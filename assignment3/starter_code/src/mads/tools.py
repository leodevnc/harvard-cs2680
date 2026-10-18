from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import fnmatch
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile


def clip(text, limit):
    if len(text) <= limit:
        return text
    marker = f'\n... [{len(text) - limit} chars omitted; request a narrower range] ...\n'
    head = max(0, (limit - len(marker)) * 2 // 3)
    tail = max(0, limit - len(marker) - head)
    return text[:head] + marker + (text[-tail:] if tail else '')


@dataclass
class ToolResult:
    text: str
    is_error: bool = False
    done: bool = False


def schema(name, description, properties, required):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties,
                           'required': required, 'additionalProperties': False}}}


STR = {'type': 'string'}
SCHEMAS = [
    schema('read_file', 'Read a UTF-8 file with line numbers; use start_line and end_line for large files.',
           {'path': STR, 'start_line': {'type': 'integer', 'minimum': 1},
            'end_line': {'type': 'integer', 'minimum': 1}}, ['path']),
    schema('search', 'Search literal text in repository files, or list files if query is empty. Ignores .git.',
           {'query': STR, 'glob': STR}, ['query']),
    schema('edit_file', 'Replace one unique exact nonempty string. Read the file first.',
           {'path': STR, 'old_string': STR, 'new_string': STR}, ['path', 'old_string', 'new_string']),
    schema('write_file', 'Create a new UTF-8 file. Refuses to overwrite existing files; use edit_file instead.',
           {'path': STR, 'content': STR}, ['path', 'content']),
    schema('bash', 'Run a shell command in the disposable task container. Do not change existing tests, access secrets, or leave the repository.',
           {'command': STR}, ['command']),
    schema('done', 'Finish after inspecting the diff and running relevant tests. Summarize changes and test evidence honestly.',
           {'summary': STR}, ['summary']),
]
BY_NAME = {s['function']['name']: s['function']['parameters'] for s in SCHEMAS}


def validate(name, args):
    if name not in BY_NAME:
        raise ValueError(f'Unknown tool: {name}')
    spec = BY_NAME[name]
    if not isinstance(args, dict):
        raise ValueError('Arguments must be an object')
    missing = set(spec['required']) - args.keys()
    extras = args.keys() - spec['properties'].keys()
    if missing or extras:
        raise ValueError(f'Missing fields: {sorted(missing)}; unexpected fields: {sorted(extras)}')
    for key, value in args.items():
        expected = spec['properties'][key]['type']
        if (expected == 'string' and not isinstance(value, str)) or (expected == 'integer' and type(value) is not int):
            raise ValueError(f'{key} must be {expected}')
        if expected == 'integer' and value < 1:
            raise ValueError(f'{key} must be positive')


class LocalBackend:
    """File tools enforce the root. Shell is opt-in and requires an external container boundary."""
    def __init__(self, workdir, allow_shell=False, timeout=60):
        self.root = Path(workdir).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('workdir must be a directory')
        self.allow_shell, self.timeout = allow_shell, timeout

    def path(self, value):
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root) or '.git' in path.relative_to(self.root).parts:
            raise ValueError('Path is outside repository or inside .git')
        return path

    def read_text(self, path):
        target = self.path(path)
        if target.stat().st_size > 2_000_000:
            raise ValueError('File exceeds 2 MB; use a narrow shell query in a container')
        return target.read_text(encoding='utf-8')

    def write_text(self, path, content):
        target = self.path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Resolve again after creating parent directories; symlink escape stays blocked.
        self.path(path).write_text(content, encoding='utf-8')

    def search(self, query, pattern='*'):
        lines = []
        count = 0
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in {'.git', 'node_modules', '.venv', '__pycache__'}
                             and not (Path(directory) / d).is_symlink())
            for name in sorted(files):
                rel = str((Path(directory) / name).relative_to(self.root))
                if not fnmatch.fnmatch(rel, pattern):
                    continue
                count += 1
                if count > 2000:
                    return '\n'.join(lines) + '\n[Scan limited to 2000 files; narrow glob]'
                try:
                    text = self.read_text(rel)
                except (OSError, ValueError, UnicodeError):
                    continue
                if not query:
                    lines.append(rel)
                else:
                    for number, line in enumerate(text.splitlines(), 1):
                        if query in line:
                            lines.append(f'{rel}:{number}: {line[:500]}')
                if len(lines) >= 200:
                    return '\n'.join(lines[:200]) + '\n[200 matches; narrow query]'
        return '\n'.join(lines) or '[No matches]'

    def exec(self, command):
        if not self.allow_shell:
            return {'stdout': '', 'stderr': 'Shell disabled. Use --allow-shell only in a disposable container.', 'exit_code': 126}
        with tempfile.TemporaryFile() as output:
            proc = subprocess.Popen(['bash', '-lc', command], cwd=self.root, stdout=output,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            timed_out = False
            try:
                proc.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            output.seek(0)
            raw = output.read(128_000)
            return {'stdout': raw.decode(errors='replace'),
                    'stderr': 'Command timed out' if timed_out else '',
                    'exit_code': 124 if timed_out else proc.returncode}


class ToolExecutor:
    def __init__(self, backend, output_limit=12000, cache_reads=False, parallel_reads=False):
        self.backend, self.output_limit = backend, output_limit
        self.cache_reads, self.parallel_reads = cache_reads, parallel_reads
        self.cache = {}
        self.cache_hits = 0

    def execute(self, name, args):
        try:
            validate(name, args)
            key = json.dumps([name, args], sort_keys=True)
            if name in {'read_file', 'search'} and self.cache_reads and key in self.cache:
                self.cache_hits += 1
                return self.cache[key]
            if name == 'read_file':
                lines = self.backend.read_text(args['path']).splitlines()
                start, end = args.get('start_line', 1), args.get('end_line', len(lines))
                if end < start and lines:
                    raise ValueError('end_line must be >= start_line')
                result = ToolResult('\n'.join(f'{i}: {s}' for i, s in enumerate(lines[start-1:end], start)) or '[Empty range]')
            elif name == 'search':
                result = ToolResult(self.backend.search(args['query'], args.get('glob', '*')))
            elif name == 'edit_file':
                self.cache.clear()
                old = args['old_string']
                text = self.backend.read_text(args['path'])
                if not old or text.count(old) != 1:
                    raise ValueError('old_string must match exactly once and must not be empty')
                self.backend.write_text(args['path'], text.replace(old, args['new_string'], 1))
                result = ToolResult('Updated ' + args['path'])
            elif name == 'write_file':
                self.cache.clear()
                try:
                    self.backend.read_text(args['path'])
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError('File exists; use edit_file')
                self.backend.write_text(args['path'], args['content'])
                result = ToolResult('Created ' + args['path'])
            elif name == 'bash':
                self.cache.clear()  # A command may write anything: never cache across it.
                value = self.backend.exec(args['command'])
                result = ToolResult(json.dumps(value, ensure_ascii=False), value['exit_code'] != 0)
            else:
                result = ToolResult(args['summary'], done=True)
            result.text = clip(result.text, self.output_limit)
            if name in {'read_file', 'search'} and self.cache_reads:
                self.cache[key] = result
            return result
        except Exception as exc:
            return ToolResult(clip(f'{type(exc).__name__}: {exc}', self.output_limit), True)

    def batch(self, calls):
        """Parallelize only contiguous read-only calls; writes are ordering barriers."""
        results, index, stopped = [], 0, False
        while index < len(calls):
            name, args = calls[index]
            if stopped:
                results.append(ToolResult('Skipped: done was already called', True))
                index += 1
                continue
            if self.parallel_reads and name in {'read_file', 'search'}:
                end = index
                while end < len(calls) and calls[end][0] in {'read_file', 'search'}:
                    end += 1
                with ThreadPoolExecutor(max_workers=min(4, end-index)) as pool:
                    results.extend(pool.map(lambda pair: self.execute(*pair), calls[index:end]))
                index = end
            else:
                result = self.execute(name, args)
                results.append(result)
                stopped = result.done
                index += 1
        return results

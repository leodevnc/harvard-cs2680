"""Adapters around the documented course Sandbox and dispatcher logger contracts.

Official archive was unavailable during authoring. Logger compatibility is checked at
runtime and fails explicitly on unknown signatures rather than dropping traces.
"""
import inspect
import json
from pathlib import PurePosixPath
import shlex


class RemoteBackend:
    def __init__(self, sandbox, workdir):
        self.sandbox = sandbox
        self.root = PurePosixPath(workdir)

    def path(self, path):
        p = PurePosixPath(path)
        if '..' in p.parts or '.git' in p.parts:
            raise ValueError('Parent traversal and .git access are forbidden')
        p = p if p.is_absolute() else self.root / p
        if not p.is_relative_to(self.root):
            raise ValueError('Outside repository')
        return str(p)

    def exec(self, command):
        result = self.sandbox.exec(command)
        if not isinstance(result, dict):
            raise TypeError('Sandbox.exec must return stdout/stderr/exit_code dict; check official adapter')
        code = result.get('exit_code', result.get('returncode'))
        if type(code) is not int:
            raise TypeError('Sandbox.exec response has no integer exit status')
        return {'stdout': result.get('stdout', ''), 'stderr': result.get('stderr', ''), 'exit_code': code}

    def read_text(self, path):
        path = self.path(path)
        # Existence probe normalizes a missing remote file to FileNotFoundError.
        check = self.exec('test -f ' + shlex.quote(path))
        if check['exit_code']:
            raise FileNotFoundError(path)
        text = self.sandbox.read_text(path)
        if not isinstance(text, str):
            raise TypeError('Sandbox.read_text must return text')
        return text

    def write_text(self, path, content):
        return self.sandbox.write_text(self.path(path), content)

    def search(self, query, pattern='*'):
        # Runs in the task container, not the agent container.
        script = '''import os,fnmatch,sys
q,pat=sys.argv[1:]; n=0
for root,dirs,files in os.walk('.',followlinks=False):
 dirs[:]=sorted(d for d in dirs if d not in {'.git','node_modules','.venv','__pycache__'} and not os.path.islink(os.path.join(root,d)))
 for f in sorted(files):
  p=os.path.join(root,f)
  if os.path.islink(p) or not fnmatch.fnmatch(p.removeprefix('./'),pat): continue
  try:
   if os.path.getsize(p)>2000000: continue
   with open(p,encoding='utf-8') as h: lines=h.read().splitlines()
  except (OSError,UnicodeError): continue
  if not q: print(p); n+=1
  else:
   for i,s in enumerate(lines,1):
    if q in s: print(f'{p}:{i}: {s[:500]}'); n+=1
    if n>=200: sys.exit()
  if n>=200: sys.exit()
'''
        result = self.exec('python3 -c ' + shlex.quote(script) + ' ' + shlex.quote(query) + ' ' + shlex.quote(pattern))
        if result['exit_code']:
            raise RuntimeError(result['stderr'])
        return result['stdout'] or '[No matches]'


def dispatcher_sink(logger):
    """Accept explicit event methods or generic log/emit/write; never guess positional order."""
    def send(row):
        event = row['event']
        fields = {k: v for k, v in row.items() if k not in {'timestamp', 'event'}}
        method = getattr(logger, event, None)
        if callable(method):
            inspect.signature(method).bind(**fields)
            method(**fields)
            return
        for name in ('log', 'emit'):
            method = getattr(logger, name, None)
            if not callable(method):
                continue
            try:
                inspect.signature(method).bind(event, **fields)
            except TypeError:
                continue
            method(event, **fields)
            return
        method = getattr(logger, 'write', None)
        if callable(method):
            inspect.signature(method).bind(row)
            method(row)
            return
        raise TypeError('Unsupported dispatcher logger signature; adapt dispatcher_sink to official trace_logger.py before leaderboard use')
    return send

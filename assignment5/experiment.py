"""Record a hypothesis before a reproducible, isolated agent workload.

Task manifest fields: id, repo, problem, test_command (argv list), optional base_commit.
Tests are evaluated by this host harness after the agent; never passed in its prompt.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'assignment2/src'))
from mads.client import ChatClient
from mads.runtime import AgentLoop, Config
from mads.tools import LocalBackend, ToolExecutor
from mads.trace import Trace


def source_hash(path):
    digest = hashlib.sha256()
    for item in sorted(path.rglob('*')):
        if not item.is_file() or any(p in {'.git', '__pycache__', '.venv'} for p in item.relative_to(path).parts):
            continue
        digest.update(str(item.relative_to(path)).encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def run_case(case, config, endpoint, output, repeat, allow_shell, manifest_dir):
    task_id = case['id']
    if not task_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in task_id):
        raise ValueError('Task id must be a safe filename')
    taskdir = output / f'{task_id}-r{repeat}'
    taskdir.mkdir(parents=True)
    original = (manifest_dir / case['repo']).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='mads-eval-') as tmp:
        repo = Path(tmp) / 'repo'
        if (original / '.git').exists():
            subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', str(original), str(repo)], check=True)
            if case.get('base_commit'):
                subprocess.run(['git', '-C', str(repo), 'checkout', '--quiet', case['base_commit']], check=True)
        else:
            shutil.copytree(original, repo, symlinks=False)
        test_command = case['test_command']
        if not isinstance(test_command, list) or not test_command or not all(isinstance(x, str) for x in test_command):
            raise ValueError('test_command must be a nonempty argv list')
        protected = case.get('protected_files')
        if not protected:
            raise ValueError('protected_files must name the test files that establish success')
        pristine = {}
        for filename in protected:
            path = (repo / filename).resolve(strict=True)
            if not path.is_relative_to(repo):
                raise ValueError('Protected file must be inside the task repository')
            pristine[filename] = path.read_bytes()
        def test(label):
            try:
                run = subprocess.run(test_command, cwd=repo, capture_output=True, text=True, timeout=120)
                (taskdir / f'{label}.log').write_text(run.stdout + run.stderr)
                return run.returncode == 0
            except subprocess.TimeoutExpired as exc:
                (taskdir / f'{label}.log').write_text('Test timeout\n')
                return False
        baseline_passed = test('before')
        cfg = Config(**config)
        executor = ToolExecutor(LocalBackend(repo, allow_shell), cfg.output_limit, cfg.cache_reads, cfg.parallel_reads)
        client = ChatClient(endpoint, os.environ.get('CS2680_API_KEY', ''))
        outcome = AgentLoop(client, executor, cfg, Trace(taskdir / 'trace.jsonl')).run(case['problem'], str(repo))
        tampered = []
        for filename, content in pristine.items():
            path = repo / filename
            if not path.exists() or path.is_symlink() or path.read_bytes() != content:
                tampered.append(filename)
                if path.is_symlink():
                    path.unlink()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        passed = test('after')
        row = {'task': task_id, 'repeat': repeat, 'baseline_passed': baseline_passed,
               'resolved': passed and not baseline_passed and not tampered and outcome.reason != 'error',
               'tests_passed': passed, 'modified_protected_files': tampered, **outcome.to_dict()}
        if (repo / '.git').exists():
            subprocess.run(['git', '-C', str(repo), 'add', '-N', '.'], check=True)
            patch = subprocess.check_output(['git', '-C', str(repo), 'diff', '--binary', 'HEAD'])
            (taskdir / 'model.diff').write_bytes(patch)
        (taskdir / 'result.json').write_text(json.dumps(row, indent=2))
        return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', type=Path, required=True)
    parser.add_argument('--agent-config', type=Path, required=True)
    parser.add_argument('--serving-config', type=Path, required=True)
    parser.add_argument('--hypothesis', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    parser.add_argument('--concurrency', type=int, default=1)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--allow-shell', action='store_true')
    args = parser.parse_args()
    if args.repeats < 1 or not 1 <= args.concurrency <= 16:
        parser.error('repeats>=1 and concurrency in 1..16 required')
    if args.output.exists():
        parser.error('Output directory already exists; choose a new one to preserve prior evidence')
    args.output.mkdir(parents=True)
    tasks = json.loads(args.tasks.read_text())
    config = json.loads(args.agent_config.read_text())
    serving = json.loads(args.serving_config.read_text())
    Config(**config)
    if len({x['id'] for x in tasks}) != len(tasks):
        parser.error('Duplicate task IDs')
    metadata = {'created_at': datetime.now(timezone.utc).isoformat(), 'hypothesis': args.hypothesis,
                'workload_sha256': hashlib.sha256(args.tasks.read_bytes()).hexdigest(),
                'source_hashes': {case['id']: source_hash((args.tasks.parent / case['repo']).resolve()) for case in tasks},
                'agent_config': config, 'serving_config': serving,
                'serving_config_verified_against_running_server': False,
                'endpoint': args.base_url, 'concurrency': args.concurrency, 'repeats': args.repeats,
                'python': sys.version, 'measurement_kind': 'real endpoint; local task tests'}
    (args.output / 'experiment.json').write_text(json.dumps(metadata, indent=2))
    start = time.monotonic()
    jobs = [(case, repeat) for repeat in range(args.repeats) for case in tasks]
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_case, case, config, args.base_url, args.output, repeat,
                               args.allow_shell, args.tasks.parent.resolve()) for case, repeat in jobs]
        rows = [f.result() for f in futures]
    metadata['wall_seconds'] = time.monotonic() - start
    (args.output / 'experiment.json').write_text(json.dumps(metadata, indent=2))
    (args.output / 'results.json').write_text(json.dumps(rows, indent=2))
    print(f'Saved {len(rows)} task runs to {args.output}')


if __name__ == '__main__':
    main()

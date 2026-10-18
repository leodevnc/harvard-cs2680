"""Host-side Docker task runner. Never mounts grading data into the agent container."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import uuid

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('index', type=int)
    args = parser.parse_args()
    task_path = Path(os.environ.get('TASKS_JSON', str(BASE / 'evaluation_scripts/agent_task_input.json')))
    tasks = json.loads(task_path.read_text())
    if not 0 <= args.index < len(tasks):
        parser.error('Task index out of range')
    iid, task = list(tasks.items())[args.index]
    if not iid or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in iid):
        parser.error('Unsafe instance_id')
    if not os.environ.get('CS2680_API_KEY'):
        parser.error('Set CS2680_API_KEY in your shell')
    image = task['docker_image']
    platform = shlex.split(os.environ.get('PLATFORM_FLAG', ''))
    pulled = subprocess.run(['docker', 'pull', *platform, image]).returncode == 0
    if not pulled:
        subprocess.run(['docker', 'image', 'inspect', image], check=True, stdout=subprocess.DEVNULL)
    logdir = BASE / 'madsLoop_logs' / iid
    logdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mads-task-') as tmp:
        tmp = Path(tmp)
        # Only task-side fields; no gold diff or held-out test data.
        (tmp / 'problem.txt').write_text(task['problem_statement'] + '\n' + task.get('requirements', '') + '\n' + task.get('interface', ''))
        name = 'mads-' + uuid.uuid4().hex[:12]
        try:
            subprocess.run(['docker', 'run', '-d', '--name', name, *platform, '--entrypoint', 'sleep',
                            '--cap-drop=ALL', '--security-opt=no-new-privileges',
                            '-e', 'CS2680_API_KEY',
                            '-v', f'{BASE / "src"}:/mads/src:ro',
                            '-v', f'{BASE / "madsLoop.py"}:/mads/madsLoop.py:ro',
                            '-v', f'{tmp}:/task-input:ro', '-v', f'{logdir}:/out', image, 'infinity'], check=True)
            # argv passes the problem directly; no shell substitution of task text.
            problem = (tmp / 'problem.txt').read_text()
            completed = subprocess.run(['docker', 'exec', '-w', '/out', name, 'python3', '/mads/madsLoop.py',
                                        '-p', problem, '--log', '--allow-shell', '--metrics', '/out/metrics.json', '/app'])
            if completed.returncode:
                print(f'Agent exited {completed.returncode}; retaining partial patch and logs')
            # Include untracked production files without committing; existing edits remain unstaged.
            subprocess.run(['docker', 'exec', name, 'git', '-C', '/app', 'add', '-N', '.'], check=True)
            patch = subprocess.check_output(['docker', 'exec', name, 'git', '-C', '/app', 'diff', '--binary', 'HEAD'])
            (BASE / f'model_patch_{iid}.diff').write_bytes(patch)
        finally:
            subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()

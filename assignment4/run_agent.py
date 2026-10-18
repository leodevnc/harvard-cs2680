"""Run A2 harness against the selected self-hosted model, with no API fallback."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-p', required=True)
    parser.add_argument('workdir')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    parser.add_argument('--config', default=str(BASE / 'configs/agent.json'))
    parser.add_argument('--allow-shell', action='store_true')
    parser.add_argument('--metrics', default='a4-metrics.json')
    args = parser.parse_args()
    host = urlparse(args.base_url).hostname
    if host not in {'127.0.0.1', 'localhost', '::1'}:
        parser.error('Only loopback self-hosted endpoints are accepted; use an SSH tunnel for a remote GPU')
    env = dict(os.environ)
    env.pop('CS2680_API_KEY', None)
    cmd = [sys.executable, str(BASE.parent / 'assignment2/madsLoop.py'), '-p', args.p,
           args.workdir, '--log', '--config', args.config, '--base-url', args.base_url,
           '--metrics', args.metrics]
    if args.allow_shell:
        cmd.append('--allow-shell')
    return subprocess.call(cmd, env=env)


if __name__ == '__main__':
    raise SystemExit(main())

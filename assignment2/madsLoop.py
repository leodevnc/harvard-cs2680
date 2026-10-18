#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import sys
import uuid
from src.mads.client import ChatClient, ScriptedClient
from src.mads.runtime import AgentLoop, Config
from src.mads.tools import LocalBackend, ToolExecutor
from src.mads.trace import Trace


def main(argv=None):
    parser = argparse.ArgumentParser(description='CS2680 madsLoop coding agent')
    parser.add_argument('-p', required=True, help='Problem statement')
    parser.add_argument('workdir', type=Path)
    parser.add_argument('--log', action='store_true')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--fixture', type=Path, help='Synthetic offline responses; not benchmark evidence')
    parser.add_argument('--allow-shell', action='store_true', help='Use ONLY in a disposable task container')
    parser.add_argument('--base-url', default=os.environ.get('CS2680_BASE_URL', 'https://api.cs2680.com/v1'))
    parser.add_argument('--model', help='Default is assignment-required qwen3.6-35b-a3b')
    parser.add_argument('--metrics', type=Path)
    args = parser.parse_args(argv)
    cfg_data = json.loads(args.config.read_text()) if args.config else {}
    if args.model:
        cfg_data['model'] = args.model
    cfg = Config(**cfg_data)
    if args.fixture:
        client = ScriptedClient(json.loads(args.fixture.read_text()))
        print('SYNTHETIC FIXTURE: not a live model run', file=sys.stderr)
    else:
        key = os.environ.get('CS2680_API_KEY', '')
        if not key and 'api.cs2680.com' in args.base_url:
            parser.error('CS2680_API_KEY is required for the course API')
        client = ChatClient(args.base_url, key)
    trace = Trace(Path('madsLoop_logs') / f'{uuid.uuid4()}.jsonl' if args.log else None)
    backend = LocalBackend(args.workdir, args.allow_shell)
    executor = ToolExecutor(backend, cfg.output_limit, cfg.cache_reads, cfg.parallel_reads)
    outcome = AgentLoop(client, executor, cfg, trace).run(args.p, args.workdir.resolve())
    print(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
    if args.metrics:
        args.metrics.parent.mkdir(parents=True, exist_ok=True)
        args.metrics.write_text(json.dumps(outcome.to_dict(), indent=2))
    return 1 if outcome.reason == 'error' else 0


if __name__ == '__main__':
    sys.exit(main())

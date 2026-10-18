"""Verify a self-hosted API really returns structured tool calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assignment2/src'))
from mads.client import ChatClient
from mads.tools import SCHEMAS


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    args = parser.parse_args()
    response = ChatClient(args.base_url, '').complete('mads-7b', [
        {'role': 'system', 'content': 'You must use the read_file tool to answer. Do not guess file contents.'},
        {'role': 'user', 'content': 'Read README.md now.'}], SCHEMAS, 256)
    message = response['choices'][0]['message']
    calls = message.get('tool_calls') or []
    if not calls:
        raise SystemExit('FAIL: no structured tool_calls. Check model template and hermes parser.')
    for call in calls:
        json.loads(call['function']['arguments'])
    print('PASS: structured tool calls returned; no tools were executed')

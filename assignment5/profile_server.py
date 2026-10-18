"""Measure streaming serving latency; completion tokens come only from response usage."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import time
import urllib.request


def request_one(base_url, model, prompt, max_tokens=256):
    body = {'model': model, 'messages': [{'role': 'system', 'content': 'You are a precise coding assistant. Give a concise answer.'},
             {'role': 'user', 'content': prompt}], 'stream': True,
            'stream_options': {'include_usage': True}, 'temperature': 0, 'max_tokens': max_tokens}
    req = urllib.request.Request(base_url.rstrip('/') + '/chat/completions', json.dumps(body).encode(),
                                 {'Content-Type': 'application/json'})
    start, first, usage, complete = time.perf_counter(), None, None, False
    with urllib.request.urlopen(req, timeout=180) as response:
        for line in response:
            if not line.startswith(b'data:'):
                continue
            data = line[5:].strip()
            if data == b'[DONE]':
                complete = True
                break
            chunk = json.loads(data)
            for choice in chunk.get('choices', []):
                delta = choice.get('delta') or {}
                if first is None and any(delta.get(k) for k in ('content', 'tool_calls', 'reasoning_content')):
                    first = time.perf_counter()
            if chunk.get('usage'):
                usage = chunk['usage']
    end = time.perf_counter()
    if not complete or first is None or not usage or type(usage.get('completion_tokens')) is not int:
        raise RuntimeError('Incomplete stream or missing usage/token timing')
    tokens = usage['completion_tokens']
    return {'ttft_s': first-start, 'latency_s': end-start,
            'tpot_s': (end-first)/(tokens-1) if tokens > 1 else None,
            'completion_tokens': tokens, 'prompt_tokens': usage['prompt_tokens']}


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values)-1)*q
    low = int(position)
    high = min(low+1, len(values)-1)
    return values[low] + (values[high]-values[low])*(position-low)


def summarize(rows, wall):
    return {'requests': len(rows), 'wall_s': wall,
            'ttft_p50_s': percentile([r['ttft_s'] for r in rows], .5),
            'ttft_p95_s': percentile([r['ttft_s'] for r in rows], .95),
            'latency_p95_s': percentile([r['latency_s'] for r in rows], .95),
            'tpot_p50_s': percentile([r['tpot_s'] for r in rows if r['tpot_s'] is not None], .5),
            'output_tokens_per_wall_s': sum(r['completion_tokens'] for r in rows)/wall if wall>0 else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    parser.add_argument('--model', default='mads-7b')
    parser.add_argument('--prompts', type=Path, required=True, help='JSON array of strings')
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prompts = json.loads(args.prompts.read_text())
    if not prompts or not all(isinstance(p,str) for p in prompts) or not 1 <= args.concurrency <= 32:
        parser.error('Nonempty prompt list and concurrency 1..32 required')
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        rows = list(pool.map(lambda p: request_one(args.base_url,args.model,p),prompts))
    summary = summarize(rows,time.perf_counter()-start)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'summary':summary,'requests':rows,'timing_note':'TPOT includes final streaming/usage framing overhead; no warmup excluded.'},indent=2))
    print(json.dumps(summary,indent=2))

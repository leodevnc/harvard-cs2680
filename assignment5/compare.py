"""Compare identical workloads without treating 'done' as task success."""
import argparse
import json
from pathlib import Path
import statistics


def summarize(metadata, rows):
    count = len(rows)
    solved = sum(r['resolved'] for r in rows)
    wall = metadata['wall_seconds']
    return {'runs': count, 'resolved': solved, 'success_rate': solved/count if count else None,
            'end_to_end_wall_s': wall, 'wall_s_per_solved': wall/solved if solved else None,
            'mean_prompt_tokens': statistics.mean(r['prompt_tokens'] for r in rows) if rows else None,
            'mean_completion_tokens': statistics.mean(r['completion_tokens'] for r in rows) if rows else None,
            'mean_model_s': statistics.mean(r['api_seconds'] for r in rows) if rows else None,
            'mean_tool_s': statistics.mean(r['tool_seconds'] for r in rows) if rows else None,
            'tool_errors': sum(r['tool_errors'] for r in rows)}


def compare(left, right):
    lm = json.loads((left/'experiment.json').read_text())
    rm = json.loads((right/'experiment.json').read_text())
    lr = json.loads((left/'results.json').read_text())
    rr = json.loads((right/'results.json').read_text())
    for key in ('workload_sha256','source_hashes','repeats'):
        if lm.get(key) != rm.get(key):
            raise ValueError(f'Cannot compare: different {key}')
    if {(r['task'],r['repeat']) for r in lr} != {(r['task'],r['repeat']) for r in rr}:
        raise ValueError('Cannot compare: task/repeat pairs differ')
    baseline, candidate = summarize(lm,lr), summarize(rm,rr)
    before = {(r['task'],r['repeat']):r['resolved'] for r in lr}
    regressions = [{'task':r['task'],'repeat':r['repeat']} for r in rr if before[(r['task'],r['repeat'])] and not r['resolved']]
    return {'baseline':baseline,'candidate':candidate,'regressions':regressions,
            'quality_preserved_on_this_sample':(not regressions and candidate['resolved']>=baseline['resolved']) if baseline['resolved'] else None,
            'note':'Sample evidence only; equal success counts do not prove equal generalization. Local test success is not official SWE-bench grading.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=json.dumps(compare(args.baseline,args.candidate),indent=2)
    if args.output:
        args.output.write_text(result)
    print(result)

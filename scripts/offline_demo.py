"""Four synthetic ESS coding tasks. Fixture responses test plumbing, not model ability."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assignment2/src'))
from mads.client import ScriptedClient
from mads.runtime import AgentLoop,Config
from mads.tools import LocalBackend,ToolExecutor
from mads.trace import Trace

CASES=[
 {'id':'soc_clamp','problem':'Clamp SOC to the inclusive [0, 100] range.',
  'before':'def clamp(soc):\n    return min(soc, 100)\n',
  'after':'def clamp(soc):\n    return max(0, min(soc, 100))\n',
  'tests':'self.assertEqual(clamp(-2),0)\n        self.assertEqual(clamp(52),52)\n        self.assertEqual(clamp(103),100)'},
 {'id':'energy_units','problem':'Convert power in kW integrated over seconds into energy in kWh.',
  'before':'def energy(kw, seconds):\n    return kw * seconds\n',
  'after':'def energy(kw, seconds):\n    return kw * seconds / 3600\n',
  'tests':'self.assertEqual(energy(100,1800),50)\n        self.assertEqual(energy(0,100),0)'},
 {'id':'discharge_efficiency','problem':'Deliverable AC energy is stored DC energy times discharge efficiency.',
  'before':'def deliverable(kwh, efficiency):\n    return kwh / efficiency\n',
  'after':'def deliverable(kwh, efficiency):\n    return kwh * efficiency\n',
  'tests':'self.assertEqual(deliverable(100,.9),90)\n        self.assertEqual(deliverable(0,.9),0)'},
 {'id':'weighted_soc','problem':'Site SOC is the capacity-weighted mean of rack SOC values.',
  'before':'def site_soc(socs, capacities):\n    return sum(socs) / len(socs)\n',
  'after':'def site_soc(socs, capacities):\n    return sum(s*c for s,c in zip(socs,capacities)) / sum(capacities)\n',
  'tests':'self.assertEqual(site_soc([20,80],[1,3]),65)\n        self.assertEqual(site_soc([50,50],[1,1]),50)'},
]


def response(name,args,index):
    return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[
      {'id':str(index),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'finish_reason':'tool_calls'}],
      'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}}


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix='ess-demo-') as tmp:
            repo=Path(tmp)
            (repo/'battery.py').write_text(case['before'])
            (repo/'test_battery.py').write_text('import unittest\nfrom battery import *\nclass TestBattery(unittest.TestCase):\n    def test_behavior(self):\n        '+case['tests']+'\n')
            def check(label):
                p=subprocess.run([sys.executable,'-B','-m','unittest','-v'],cwd=repo,capture_output=True,text=True)
                (output/f"{case['id']}.{label}.log").write_text(p.stdout+p.stderr)
                return p.returncode==0
            before=check('before')
            responses=[response('read_file',{'path':'battery.py'},1),
                       response('edit_file',{'path':'battery.py','old_string':case['before'],'new_string':case['after']},2),
                       response('done',{'summary':'Applied scripted replacement. Host verifier runs tests next.'},3)]
            result=AgentLoop(ScriptedClient(responses),ToolExecutor(LocalBackend(repo)),
                             Config(),Trace(output/f"{case['id']}.jsonl")).run(case['problem'],str(repo))
            after=check('after')
            rows.append({'task':case['id'],'baseline_passed':before,'after_passed':after,'reason':result.reason,
                         'measurement_kind':'synthetic scripted client; real local file edits and tests'})
    (output/'summary.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2))
    if not all(not r['baseline_passed'] and r['after_passed'] for r in rows):
        raise SystemExit('Offline integration demo failed')
    return rows


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'test-results/offline-demo')
    run(parser.parse_args().output)

"""Create four synthetic ESS tasks for A4/A5 live experiments (not official A2 mytest)."""
import json
from pathlib import Path
from offline_demo import CASES

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'assignment5/workloads/ess'
target.mkdir(parents=True,exist_ok=True)
manifest=[]
for case in CASES:
    folder=target/case['id']
    folder.mkdir(exist_ok=True)
    (folder/'battery.py').write_text(case['before'])
    (folder/'test_battery.py').write_text('import unittest\nfrom battery import *\nclass TestBattery(unittest.TestCase):\n    def test_behavior(self):\n        '+case['tests']+'\n')
    manifest.append({'id':case['id'],'repo':'ess/'+case['id'],'problem':case['problem'],
                     'test_command':['python3','-B','-m','unittest','-v'],'protected_files':['test_battery.py']})
(target.parent/'ess.json').write_text(json.dumps(manifest,indent=2))
(target.parent/'prompts.json').write_text(json.dumps([c['problem']+' Explain the Python implementation.' for c in CASES]*3,indent=2))
print('Created synthetic ESS workload at',target.parent)

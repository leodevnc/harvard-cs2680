"""Verify a user-supplied task in a fresh container using JUnit test identities.

tasks.json contains task-side fields; task_test.json additionally provides test_command
(argv list) and junit_path for this verifier. Grading labels never reach the model.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent


def junit_results(path):
    tree = ET.parse(path)
    results = {}
    for case in tree.iter('testcase'):
        name = case.get('classname','') + '::' + case.get('name','')
        if name in results:
            raise ValueError('Duplicate JUnit test identity: ' + name)
        results[name] = not any(case.find(tag) is not None for tag in ('failure','error','skipped'))
    return results


def resolved(results, spec):
    required = spec['fail_to_pass'] + spec['pass_to_pass']
    return bool(spec['fail_to_pass']) and all(results.get(name) is True for name in required)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('instance_id')
    parser.add_argument('patch', nargs='?', type=Path)
    parser.add_argument('--tasks', type=Path, default=BASE/'tasks.json')
    parser.add_argument('--tests', type=Path, default=BASE/'task_test.json')
    args=parser.parse_args()
    task=json.loads(args.tasks.read_text())[args.instance_id]
    spec=json.loads(args.tests.read_text())[args.instance_id]
    name='mads-verify-'+uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        try:
            subprocess.run(['docker','run','-d','--network=none','--name',name,'--entrypoint','sleep',task['docker_image'],'infinity'],check=True)
            def run(*argv,check=True):
                return subprocess.run(['docker','exec','-w','/app',name,*argv],check=check)
            run('bash','-lc',spec['before_repo_set_cmd'])
            if args.patch:
                subprocess.run(['docker','cp',str(args.patch.resolve()),name+':/tmp/agent.diff'],check=True)
                run('git','apply','--check','/tmp/agent.diff')
                run('git','apply','/tmp/agent.diff')
            # Restore the pristine test files after applying the patch.
            for filename in spec['selected_test_files_to_run']:
                run('git','checkout','HEAD','--',filename)
            run(*spec['test_command'],check=False)
            subprocess.run(['docker','cp',name+':'+spec['junit_path'],str(tmp/'tests.xml')],check=True)
            results=junit_results(tmp/'tests.xml')
            print(json.dumps(results,indent=2))
            success=resolved(results,spec)
            print('RESOLVED' if success else 'unresolved')
            raise SystemExit(0 if success else 1)
        finally:
            subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

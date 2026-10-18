import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from assignment5 import experiment
from assignment5.compare import compare
from scripts import install_official


def tool_response(name,args,id):
    return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[
        {'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}}],
            'usage':{'prompt_tokens':12,'completion_tokens':4,'total_tokens':16}}


class ExperimentTest(unittest.TestCase):
    def test_real_edits_and_external_tests_in_isolated_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);repo=root/'source';repo.mkdir();out=root/'out';out.mkdir()
            (repo/'calc.py').write_text('def add(a,b):\n    return a-b\n')
            (repo/'test_calc.py').write_text('import unittest\nfrom calc import add\nclass T(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n')
            case={'id':'add','repo':'source','problem':'Fix add','test_command':['python3','-B','-m','unittest'],
                  'protected_files':['test_calc.py']}
            from mads.client import ScriptedClient
            fixture=ScriptedClient([tool_response('edit_file',{'path':'calc.py','old_string':'a-b','new_string':'a+b'},'1'),
                                    tool_response('done',{'summary':'fixed'},'2')])
            with patch.object(experiment,'ChatClient',return_value=fixture):
                row=experiment.run_case(case,{},'http://fake',out,0,False,root)
            self.assertTrue(row['resolved'])
            self.assertFalse(row['baseline_passed'])
            self.assertIn('a-b',(repo/'calc.py').read_text())

    def test_protected_test_edit_cannot_score_as_success(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);repo=root/'source';repo.mkdir();out=root/'out';out.mkdir()
            (repo/'test_bad.py').write_text('raise RuntimeError("failure")\n')
            case={'id':'tamper','repo':'source','problem':'Fix bug','test_command':['python3','-B','test_bad.py'],
                  'protected_files':['test_bad.py']}
            from mads.client import ScriptedClient
            fixture=ScriptedClient([tool_response('edit_file',{'path':'test_bad.py','old_string':'raise RuntimeError("failure")','new_string':'pass'},'1'),
                                    tool_response('done',{'summary':'fake success'},'2')])
            with patch.object(experiment,'ChatClient',return_value=fixture):
                row=experiment.run_case(case,{},'http://fake',out,0,False,root)
            self.assertFalse(row['resolved'])
            self.assertEqual(row['modified_protected_files'],['test_bad.py'])

    def test_equal_success_count_with_regression_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            left,right=Path(d)/'left',Path(d)/'right';left.mkdir();right.mkdir()
            meta={'wall_seconds':2,'workload_sha256':'same','source_hashes':{'a':'x','b':'y'},'repeats':1}
            common={'repeat':0,'prompt_tokens':10,'completion_tokens':5,'api_seconds':1,'tool_seconds':.1,'tool_errors':0}
            for path,flags in [(left,[True,False]),(right,[False,True])]:
                (path/'experiment.json').write_text(json.dumps(meta))
                (path/'results.json').write_text(json.dumps([dict(common,task=t,resolved=f) for t,f in zip(['a','b'],flags)]))
            result=compare(left,right)
            self.assertFalse(result['quality_preserved_on_this_sample'])
            self.assertEqual(result['regressions'],[{'task':'a','repeat':0}])

    def test_installer_preserves_implementation_and_blocks_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def archive(name,content,target):
                with tarfile.open(target,'w:gz') as tar:
                    data=content.encode();member=tarfile.TarInfo(name);member.size=len(data)
                    tar.addfile(member,io.BytesIO(data))
            tarpath=root/'starter.tar.gz'
            existing=root/'assignment2/madsLoop.py';existing.parent.mkdir();existing.write_text('ours')
            archive('assignment2/madsLoop.py','theirs',tarpath)
            with patch.object(install_official,'ROOT',root):
                install_official.install(2,tarpath)
                self.assertEqual(existing.read_text(),'ours')
                archive('assignment2/../../escape','bad',tarpath)
                with self.assertRaises(ValueError):install_official.install(2,tarpath)

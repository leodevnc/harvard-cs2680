import http.server
import json
from pathlib import Path
import socketserver
import tempfile
import threading
import unittest
from assignment2.src.mads.client import ChatClient, APIError
from assignment2.src.mads.runtime import AgentLoop,Config
from assignment2.src.mads.tools import LocalBackend,ToolExecutor
from assignment2.mytest.verify import junit_results,resolved
from assignment4.serve import command
from assignment5.compare import compare,summarize
from assignment5.profile_server import request_one,summarize as server_summary


class FakeAPI(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if payload['model']=='auth-error':
            self.send_response(401);self.end_headers();return
        if payload.get('stream'):
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            chunks=[{'choices':[{'delta':{'role':'assistant'}}]},
                    {'choices':[{'delta':{'content':'hello'}}]},
                    {'choices':[],'usage':{'prompt_tokens':10,'completion_tokens':2}}]
            for chunk in chunks:
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
            self.wfile.write(b'data: [DONE]\n\n');return
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        value={'choices':[{'message':{'role':'assistant','content':'hello'},'finish_reason':'stop'}],
               'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}}
        self.wfile.write(json.dumps(value).encode())


class HTTPTest(unittest.TestCase):
    def setUp(self):
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),FakeAPI)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/v1'
    def tearDown(self):self.server.shutdown();self.server.server_close()
    def test_live_wire_protocol_against_fake_http(self):
        client=ChatClient(self.url,'test-placeholder')
        self.assertEqual(client.complete('mads-7b',[],[],20)['usage']['total_tokens'],12)
        with self.assertRaises(APIError) as ctx:client.complete('auth-error',[],[],20)
        self.assertFalse(ctx.exception.retryable)
    def test_stream_metrics(self):
        row=request_one(self.url,'mads-7b','hello')
        self.assertGreaterEqual(row['ttft_s'],0)
        self.assertGreaterEqual(row['latency_s'],row['ttft_s'])
        self.assertEqual(row['completion_tokens'],2)
        summary=server_summary([row],1)
        self.assertEqual(summary['output_tokens_per_wall_s'],2)


class OtherTest(unittest.TestCase):
    def test_junit_no_false_success_on_missing_or_skipped_tests(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'tests.xml'
            path.write_text('<testsuite><testcase classname="a" name="ok"/><testcase classname="a" name="skip"><skipped/></testcase></testsuite>')
            result=junit_results(path)
            self.assertTrue(resolved(result,{'fail_to_pass':['a::ok'],'pass_to_pass':[]}))
            self.assertFalse(resolved(result,{'fail_to_pass':['missing'],'pass_to_pass':[]}))
            self.assertFalse(resolved(result,{'fail_to_pass':['a::skip'],'pass_to_pass':[]}))
    def test_serving_config_is_local_and_small_model(self):
        config=json.loads(Path('assignment4/configs/baseline.json').read_text())
        cmd=command(config)
        self.assertIn('127.0.0.1:8000:8000',cmd)
        self.assertIn('hermes',cmd)
        self.assertIn('--no-enable-prefix-caching',cmd)
        config['model']='larger-model'
        with self.assertRaises(ValueError):command(config)
    def test_comparison_requires_same_workload_and_reports_zero_success(self):
        self.assertIsNone(summarize({'wall_seconds':10},[])['wall_s_per_solved'])
        with tempfile.TemporaryDirectory() as d:
            left,right=Path(d)/'a',Path(d)/'b';left.mkdir();right.mkdir()
            for i,path in enumerate([left,right]):
                (path/'experiment.json').write_text(json.dumps({'workload_sha256':str(i),'wall_seconds':2,'repeats':1}))
                (path/'results.json').write_text('[]')
            with self.assertRaises(ValueError):compare(left,right)

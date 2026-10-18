import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from server import App, make_server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(self.temp.name, replay_delay=.001)
        self.app.archive = Path(self.temp.name) / 'archive'
        self.server = make_server(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, data, headers=None, path='/api/run'):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('POST', path, json.dumps(data), headers or {'X-Mads-Lens':'1'})
        res = conn.getresponse()
        body = res.read().decode()
        conn.close()
        return res.status, body

    def events(self, data):
        status, body = self.request(data)
        self.assertEqual(status, 200)
        return [json.loads(x) for x in body.splitlines()]

    def test_replay_resume_and_archive(self):
        data = {'prompt':'test', 'cwd':'.', 'mode':'replay'}
        events = self.events(data)
        self.assertEqual(events[-1]['subtype'], 'success')
        events2 = self.events(dict(data, session_id='replay-session'))
        self.assertEqual(events2[-1]['session_id'], 'replay-session')
        self.assertEqual(len(list(self.app.archive.glob('*.jsonl'))), 2)

    def test_invalid_directory_origin_and_resume(self):
        self.assertEqual(self.request({'prompt':'x', 'cwd':'..'})[0], 400)
        self.assertEqual(self.request({'prompt':'x'}, {'X-Mads-Lens':'1','Origin':'https://evil.example'})[0], 403)
        self.assertEqual(self.request({'prompt':'x'}, {'Content-Type':'application/json'})[0], 403)
        self.assertEqual(self.request({'prompt':'x', 'session_id':'unknown'})[0],400)

    def test_missing_executable_and_failure_fixture(self):
        self.app.claude = '/does-not-exist/claude'
        self.assertEqual(self.events({'prompt':'x','mode':'live'})[-1]['type'], 'lens_error')
        self.assertTrue(self.events({'prompt':'x','mode':'failure'})[-1]['is_error'])

    def test_real_subprocess_stream_and_resume_args(self):
        fake = Path(self.temp.name) / 'claude'
        fake.write_text('#!/usr/bin/env python3\nimport json,sys,time\nprint(json.dumps({"type":"system","session_id":"fake-live"}),flush=True)\ntime.sleep(.2)\nprint(json.dumps({"type":"result","subtype":"success","session_id":"fake-live","result":sys.argv}),flush=True)\n')
        fake.chmod(0o755)
        self.app.claude = str(fake)
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('POST','/api/run',json.dumps({'prompt':'first','mode':'live'}),{'X-Mads-Lens':'1'})
        res = conn.getresponse()
        self.assertEqual(json.loads(res.readline())['type'],'lens_start')
        self.assertEqual(json.loads(res.readline())['session_id'],'fake-live')
        self.assertIsNone(self.app.active['process'].poll())
        self.assertEqual(self.request({'prompt':'overlap','mode':'live'})[0],409)
        res.read();conn.close()
        end = self.events({'prompt':'followup','mode':'live','session_id':'fake-live'})[-1]
        self.assertIn('--resume', end['result'])
        self.assertIn('fake-live', end['result'])

    def test_timeout_and_stop(self):
        fake = Path(self.temp.name) / 'claude'
        fake.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(20)\n')
        fake.chmod(0o755)
        self.app.claude = str(fake)
        self.app.timeout = .15
        self.assertIn('시간 제한', self.events({'prompt':'x','mode':'live'})[-1]['message'])
        self.app.timeout = 10
        result = []
        thread = threading.Thread(target=lambda: result.extend(self.events({'prompt':'x','mode':'live'})))
        thread.start()
        deadline=time.monotonic()+3
        while self.app.active is None and time.monotonic()<deadline:
            time.sleep(.01)
        self.request({},path='/api/stop')
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertIn('중단', result[-1]['message'])


if __name__ == '__main__':
    unittest.main()

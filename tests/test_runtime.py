import json
from pathlib import Path
import tempfile
import unittest
from assignment2.src.mads.client import APIError,ScriptedClient
from assignment2.src.mads.runtime import AgentLoop,Config,compact
from assignment2.src.mads.tools import LocalBackend,ToolExecutor,clip
from assignment2.src.mads.trace import Trace,FIELDS


def response(calls=None,content=None):
    return {'choices':[{'message':{'role':'assistant','content':content,'tool_calls':calls or []},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}


def call(name,args,id='1'):
    return {'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'battery.py').write_text('value = 1\n')
        self.executor=ToolExecutor(LocalBackend(self.root),cache_reads=True,parallel_reads=True)

    def tearDown(self):
        self.tmp.cleanup()

    def loop(self,responses,**kwargs):
        client=ScriptedClient(responses)
        rows=[]
        agent=AgentLoop(client,self.executor,Config(**kwargs),Trace(callback=rows.append),sleep=lambda _:None)
        result=agent.run('Fix value','.')
        return result,agent,client,rows

    def test_edit_and_done(self):
        result,agent,client,rows=self.loop([
            response([call('read_file',{'path':'battery.py'})]),
            response([call('edit_file',{'path':'battery.py','old_string':'1','new_string':'2'})]),
            response([call('done',{'summary':'fixed'})])])
        self.assertEqual(result.reason,'done')
        self.assertEqual((self.root/'battery.py').read_text(),'value = 2\n')
        self.assertEqual(result.prompt_tokens,30)
        for row in rows:
            self.assertEqual(set(row)-{'event','timestamp'},FIELDS[row['event']])
        for message in client.requests[1:]:
            for i,item in enumerate(message):
                if item.get('tool_calls'):
                    self.assertEqual(message[i+1]['tool_call_id'],item['tool_calls'][0]['id'])

    def test_malformed_arguments_and_unknown_tool_recover(self):
        malformed=call('read_file',{})
        malformed['function']['arguments']='{oops'
        result,agent,client,rows=self.loop([response([malformed,call('made_up',{},'2')]),response(content='cannot proceed')])
        self.assertEqual(result.reason,'no_tool_calls')
        self.assertEqual(result.tool_errors,2)
        self.assertEqual(len([x for x in agent.messages if x['role']=='tool']),2)

    def test_retry_and_auth_fail_fast(self):
        result,_,_,rows=self.loop([APIError('rate limit',True),response(content='ok')],retry_base_s=0)
        self.assertEqual(result.retries,1)
        self.assertEqual(result.reason,'no_tool_calls')
        result,_,_,_=self.loop([APIError('401',False)])
        self.assertEqual(result.reason,'error')
        self.assertEqual(result.retries,0)

    def test_bad_envelope_and_missing_usage(self):
        result,_,_,_=self.loop([{},response(content='ok')],retry_base_s=0)
        self.assertEqual(result.reason,'no_tool_calls')
        data=response(content='ok');data.pop('usage')
        result,_,_,_=self.loop([data])
        self.assertEqual(result.reason,'error')

    def test_duplicate_ids_fail_before_side_effect(self):
        result,_,_,_=self.loop([response([call('edit_file',{'path':'battery.py','old_string':'1','new_string':'9'}),call('done',{'summary':'x'})])])
        self.assertEqual(result.reason,'error')
        self.assertEqual((self.root/'battery.py').read_text(),'value = 1\n')

    def test_iteration_token_and_stall_limits(self):
        r=response([call('read_file',{'path':'battery.py'})])
        result,_,_,_=self.loop([r]*3,max_iterations=2)
        self.assertEqual(result.reason,'iteration_limit')
        result,_,_,_=self.loop([r]*3,max_total_tokens=10)
        self.assertEqual(result.reason,'token_limit')
        result,_,_,_=self.loop([r]*8,stall_limit=2)
        self.assertEqual(result.reason,'stalled')

    def test_compaction_preserves_pairs(self):
        messages=[{'role':'system','content':'s'},{'role':'user','content':'task'}]
        for i in range(10):
            messages.extend([{'role':'assistant','tool_calls':[call('read_file',{'path':'battery.py'},str(i))]},
                             {'role':'tool','tool_call_id':str(i),'content':'x'*3000}])
        shrunk,changed=compact(messages,5000)
        self.assertTrue(changed)
        self.assertLessEqual(len(json.dumps(shrunk)),5000)
        for index,item in enumerate(shrunk):
            if item['role']=='tool':
                self.assertEqual(shrunk[index-1]['tool_calls'][0]['id'],item['tool_call_id'])

    def test_path_traversal_symlink_and_git(self):
        for path in ['../secret','/etc/passwd','.git/config']:
            self.assertTrue(self.executor.execute('read_file',{'path':path}).is_error)
        (self.root/'outside').symlink_to('/etc/passwd')
        self.assertTrue(self.executor.execute('read_file',{'path':'outside'}).is_error)

    def test_edit_uniqueness_and_create(self):
        self.assertTrue(self.executor.execute('edit_file',{'path':'battery.py','old_string':'','new_string':'x'}).is_error)
        self.assertTrue(self.executor.execute('write_file',{'path':'battery.py','content':'bad'}).is_error)
        self.assertFalse(self.executor.execute('write_file',{'path':'new.py','content':'new'}).is_error)

    def test_cache_invalidation_and_batch_order(self):
        self.executor.execute('read_file',{'path':'battery.py'})
        self.executor.execute('read_file',{'path':'battery.py'})
        self.assertEqual(self.executor.cache_hits,1)
        results=self.executor.batch([('read_file',{'path':'battery.py'}),
            ('edit_file',{'path':'battery.py','old_string':'1','new_string':'3'}),
            ('read_file',{'path':'battery.py'})])
        self.assertIn('value = 1',results[0].text)
        self.assertIn('value = 3',results[2].text)

    def test_shell_disabled_and_done_barrier(self):
        self.assertTrue(self.executor.execute('bash',{'command':'echo x'}).is_error)
        r=self.executor.batch([('done',{'summary':'done'}),('edit_file',{'path':'battery.py','old_string':'1','new_string':'4'})])
        self.assertTrue(r[1].is_error)
        self.assertEqual((self.root/'battery.py').read_text(),'value = 1\n')

    def test_truncation_is_exactly_what_trace_and_model_receive(self):
        (self.root/'big.txt').write_text('a'*40000)
        self.executor.output_limit=500
        result,agent,client,rows=self.loop([response([call('read_file',{'path':'big.txt'})]),response(content='ok')])
        text=next(x['result'] for x in rows if x['event']=='tool_result')
        self.assertEqual(text,client.requests[1][-1]['content'])
        self.assertLessEqual(len(text),500)


if __name__=='__main__':unittest.main()

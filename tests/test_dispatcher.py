import json
from pathlib import Path
import tempfile
import unittest
from assignment2.src.mads.tools import LocalBackend
from assignment3.starter_code.src.agentic_loop import Agent
from assignment3.starter_code.src.budget import Budget,BudgetClient
from assignment3.starter_code.src.adapters import dispatcher_sink
from assignment3.starter_code.src.mads.client import ScriptedClient,APIError


def finish():
    return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[
        {'id':'done-1','type':'function','function':{'name':'done','arguments':'{"summary":"synthetic attempt"}'}}]}}],
        'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}


class Logger:
    def __init__(self):self.rows=[]
    def log(self,event,**fields):self.rows.append({'event':event,**fields})


class Dispatcher:
    def __init__(self,root,grades):
        self.root,self.grades=root,iter(grades)
        self.opened=False;self.calls=[];self.trace=Logger()
    def next_task(self):
        if self.opened:return None
        self.opened=True
        return {'task':0,'workdir':str(self.root),'sandbox_url':'fake://sandbox','problem_statement':'Synthetic task'}
    def logger(self,k):return self.trace
    def extract_patch(self,k):self.calls.append('patch')
    def evaluate(self,k):self.calls.append('evaluate');return next(self.grades)
    def continue_task(self,k):self.calls.append('continue')
    def done(self,k,reason,iterations):self.calls.append(('done',reason,iterations))


class DispatcherTest(unittest.TestCase):
    def test_grade_continue_then_expert(self):
        with tempfile.TemporaryDirectory() as d:
            dispatcher=Dispatcher(Path(d),[{'tests_total':2,'tests_failed':1},{'tests_total':2,'tests_failed':0}])
            cfg={'base_url':'fake','api_key':'','standard':'standard','starter':'starter','expert':'expert',
                 'workers':1,'max_attempts':2,'budget_usd':1}
            client=ScriptedClient([finish(),finish()])
            agent=Agent(dispatcher,config=cfg,client_factory=lambda:client,
                        sandbox_factory=lambda url,workdir:LocalBackend(workdir,allow_shell=True))
            result=agent.run()
            self.assertEqual(result[0]['reason'],'resolved')
            self.assertEqual(dispatcher.calls,['patch','evaluate','continue','patch','evaluate',('done','resolved',2)])
            self.assertEqual(len([x for x in dispatcher.trace.rows if x['event']=='api_request']),2)
            self.assertGreater(agent.budget.spent,0)
    def test_zero_graded_tests_are_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            dispatcher=Dispatcher(Path(d),[{'tests_total':0,'tests_failed':0}])
            cfg={'base_url':'fake','api_key':'','standard':'standard','starter':'starter','expert':'expert',
                 'workers':1,'max_attempts':1,'budget_usd':1}
            agent=Agent(dispatcher,config=cfg,client_factory=lambda:ScriptedClient([finish()]),
                        sandbox_factory=lambda url,workdir:LocalBackend(workdir))
            self.assertEqual(agent.run()[0]['reason'],'tests_failed')
    def test_budget_refuses_before_api_call(self):
        budget=Budget(.000001)
        client=ScriptedClient([finish()])
        wrapped=BudgetClient(client,budget,{'expert':'expert'})
        with self.assertRaises(APIError):wrapped.complete('expert',[],[],100)
        self.assertEqual(len(client.requests),0)
        self.assertEqual(budget.reserved,0)
    def test_unsupported_logger_fails_explicitly(self):
        with self.assertRaises(TypeError):dispatcher_sink(object())({'event':'run_end','reason':'done','num_iterations':1})

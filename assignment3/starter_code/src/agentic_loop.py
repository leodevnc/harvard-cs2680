"""Assignment 3 entry point. Only this src/ directory is needed by the course runner."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
from .adapters import RemoteBackend, dispatcher_sink
from .budget import Budget, BudgetClient
from .config import settings
from .mads.client import ChatClient
from .mads.runtime import AgentLoop, Config
from .mads.tools import ToolExecutor
from .mads.trace import Trace


class Agent:
    def __init__(self, dispatcher, *, config=None, client_factory=None, sandbox_factory=None):
        self.dispatcher = dispatcher
        self.settings = config or settings()
        if not 1 <= self.settings['workers'] <= 5 or not 1 <= self.settings['max_attempts'] <= 3:
            raise ValueError('workers must be 1..5 and max_attempts 1..3')
        self.client_factory = client_factory or (lambda: ChatClient(self.settings['base_url'], self.settings['api_key']))
        if sandbox_factory is None:
            # Official file is installed by scripts/install_official.py; we preserve it.
            from .sandbox import Sandbox
            sandbox_factory = Sandbox
        self.sandbox_factory = sandbox_factory
        self.lock, self.stop = threading.Lock(), threading.Event()
        self.budget = Budget(self.settings['budget_usd'])
        self.results = []

    def run(self):
        self.started = time.monotonic()
        with ThreadPoolExecutor(max_workers=self.settings['workers']) as pool:
            futures = [pool.submit(self.worker) for _ in range(self.settings['workers'])]
            for future in futures:
                future.result()
        return self.results

    def worker(self):
        while not self.stop.is_set() and time.monotonic() - self.started < 3.8 * 3600:
            with self.lock:
                if self.budget.spent >= self.budget.limit:
                    self.stop.set(); return
                spec = self.dispatcher.next_task()
            if spec is None:
                return
            self.solve(spec)

    def solve(self, spec):
        k, workdir = spec['task'], spec['workdir']
        sandbox = self.sandbox_factory(spec['sandbox_url'], workdir)
        backend = RemoteBackend(sandbox, workdir)
        logger = self.dispatcher.logger(k)
        sink = dispatcher_sink(logger)
        trace = Trace(callback=sink)
        model_tiers = {self.settings[tier]: tier for tier in ('starter', 'standard', 'expert')}
        client = BudgetClient(self.client_factory(), self.budget, model_tiers)
        cfg = Config(model=self.settings['standard'], max_iterations=35, max_total_tokens=180000,
                     max_context_chars=65000, output_limit=6000, cache_reads=True, parallel_reads=True,
                     timeout_s=900)
        prompt = '\n'.join(str(spec.get(key, '')) for key in ('problem_statement', 'requirements', 'interface'))
        total_iterations, feedback, final_reason, evaluation = 0, None, 'error', None
        try:
            for attempt in range(self.settings['max_attempts']):
                executor = ToolExecutor(backend, cfg.output_limit, cfg.cache_reads, cfg.parallel_reads)
                def select_model(iteration, outcome):
                    return self.settings['expert'] if attempt > 0 or outcome.tool_errors >= 3 else self.settings['standard']
                outcome = AgentLoop(client, executor, cfg, trace, select_model).run(prompt, workdir, feedback)
                total_iterations += outcome.iterations
                if outcome.reason == 'error':
                    final_reason = outcome.summary
                    if 'budget exhausted' in final_reason:
                        self.stop.set()
                    break
                self.dispatcher.extract_patch(k)
                evaluation = self.dispatcher.evaluate(k)
                if evaluation.get('tests_total', 0) > 0 and evaluation.get('tests_failed') == 0:
                    final_reason = 'resolved'; break
                final_reason = 'tests_failed'
                if attempt + 1 < self.settings['max_attempts']:
                    self.dispatcher.continue_task(k)
                    feedback = ('Previous attempt summary:\n' + outcome.summary[:3000] +
                                '\nGrader counts (no hidden tests available): ' + json.dumps(evaluation) +
                                '\nRepository edits remain. Inspect the current diff and diagnose the failure; do not repeat the same patch.')
        finally:
            self.dispatcher.done(k, final_reason, total_iterations)
            with self.lock:
                self.results.append({'task': k, 'reason': final_reason, 'iterations': total_iterations, 'evaluation': evaluation})

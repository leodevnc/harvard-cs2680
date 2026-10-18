import json
import threading
from .mads.client import APIError

# Assignment 3's published rates, USD per 1M tokens; configure new rates when the course changes them.
RATES = {'expert': (2.0, .10, 10.0), 'standard': (.08, .004, .28), 'starter': (.01, .0005, .04)}


class Budget:
    def __init__(self, limit):
        if limit <= 0:
            raise ValueError('Budget must be positive')
        self.limit, self.spent, self.reserved = limit, 0.0, 0.0
        self.lock = threading.Lock()

    def reserve(self, amount):
        with self.lock:
            if self.spent + self.reserved + amount > self.limit:
                raise APIError('Harness dollar budget exhausted')
            self.reserved += amount

    def settle(self, reserved, actual):
        with self.lock:
            self.reserved -= reserved
            self.spent += actual


class BudgetClient:
    def __init__(self, client, budget, model_tiers):
        self.client, self.budget, self.model_tiers = client, budget, model_tiers

    def complete(self, model, messages, tools, max_tokens):
        rates = RATES[self.model_tiers[model]]
        # UTF-8 byte count + framing allowance is a conservative estimate, not tokenizer telemetry.
        estimated_input = len(json.dumps([messages, tools], ensure_ascii=False).encode()) + 1024
        reserve = (estimated_input * rates[0] + max_tokens * rates[2]) / 1e6
        self.budget.reserve(reserve)
        actual = reserve
        try:
            response = self.client.complete(model, messages, tools, max_tokens)
            usage = response.get('usage') or {}
            if all(type(usage.get(k)) is int for k in ('prompt_tokens', 'completion_tokens')):
                p, c = usage['prompt_tokens'], usage['completion_tokens']
                cached = min(p, max(0, (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)))
                actual = ((p-cached)*rates[0] + cached*rates[1] + c*rates[2]) / 1e6
            return response
        finally:
            # Unknown billing after transport failures is conservatively charged to the local budget.
            self.budget.settle(reserve, actual)

from datetime import datetime, timezone
import json
from pathlib import Path
import threading

FIELDS = {
    'run_start': {'model_id', 'workdir'},
    'api_request': {'iteration', 'prompt_tokens', 'completion_tokens', 'total_tokens'},
    'api_retry': {'iteration', 'error', 'backoff_s'},
    'tool_call': {'iteration', 'tool_name', 'arguments'},
    'tool_result': {'iteration', 'tool_name', 'result', 'is_error'},
    'run_end': {'reason', 'num_iterations'},
}


class Trace:
    def __init__(self, path=None, callback=None):
        self.path, self.callback = Path(path) if path else None, callback
        self.lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event, **fields):
        if event not in FIELDS or fields.keys() != FIELDS[event]:
            raise ValueError(f'Invalid trace fields for {event}: {fields.keys()}')
        row = {'timestamp': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
        with self.lock:
            if self.path:
                with self.path.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            if self.callback:
                self.callback(row)

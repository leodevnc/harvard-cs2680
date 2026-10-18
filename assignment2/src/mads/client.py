import json
import urllib.error
import urllib.request
from urllib.parse import urlparse


class APIError(RuntimeError):
    def __init__(self, message, retryable=False, retry_after=None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ChatClient:
    """OpenAI-compatible wire protocol, without an SDK dependency."""
    def __init__(self, base_url, api_key, timeout=120, extra_headers=None):
        parsed = urlparse(base_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise ValueError('base_url must be an HTTP(S) endpoint')
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.key, self.timeout = api_key, timeout
        self.headers = extra_headers or {}
        self.opener = urllib.request.build_opener(NoRedirect)

    def complete(self, model, messages, tools, max_tokens):
        payload = {'model': model, 'messages': messages, 'tools': tools,
                   'tool_choice': 'auto', 'temperature': 0, 'max_tokens': max_tokens}
        headers = {'Content-Type': 'application/json', **self.headers}
        if self.key:
            headers['Authorization'] = 'Bearer ' + self.key
        req = urllib.request.Request(self.url, json.dumps(payload).encode(), headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                data = response.read(16 * 1024 * 1024 + 1)
                if len(data) > 16 * 1024 * 1024:
                    raise APIError('Model response exceeds 16 MiB')
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            # Do not expose provider bodies, which may echo secrets or requests.
            delay = exc.headers.get('Retry-After')
            exc.close()
            raise APIError(f'Model HTTP {exc.code}', exc.code in {408, 409, 429} or exc.code >= 500,
                           float(delay) if delay and delay.isdigit() else None) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise APIError(f'Model transport error: {type(exc).__name__}', True) from exc
        except (ValueError, UnicodeError) as exc:
            raise APIError('Model returned invalid JSON', True) from exc


class ScriptedClient:
    """Explicit synthetic responses for offline runtime tests, never a model benchmark."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def complete(self, model, messages, tools, max_tokens):
        self.requests.append(json.loads(json.dumps(messages)))
        try:
            result = next(self.responses)
        except StopIteration as exc:
            raise APIError('Synthetic fixture exhausted') from exc
        if isinstance(result, Exception):
            raise result
        return result

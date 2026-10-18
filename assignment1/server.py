"""Mads-Lens: loopback-only Claude Code stream viewer (Python 3.10+)."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent


class App:
    def __init__(self, workspace, claude="claude", timeout=900, replay_delay=.15):
        self.workspace = Path(workspace).resolve(strict=True)
        self.claude, self.timeout, self.replay_delay = claude, timeout, replay_delay
        self.lock = threading.Lock()
        self.active = None
        self.sessions = {}  # session ID -> (resolved cwd, mode)
        self.archive = BASE / ".runs"

    def directory(self, value):
        path = (self.workspace / value).resolve(strict=True)
        if not path.is_dir() or not path.is_relative_to(self.workspace):
            raise ValueError("작업 폴더는 --workspace 내부 디렉터리여야 합니다.")
        return path

    def command(self, prompt, session):
        cmd = [self.claude, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--allowedTools", "Read,Glob,Grep,Edit,Write,Bash(python -m unittest*),Agent,Task"]
        if session:
            cmd.extend(["--resume", session])
        return cmd


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def app(self):
        return self.server.app

    def reply(self, status, body, mime="application/json; charset=utf-8"):
        self.close_connection = True
        data = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def host_ok(self):
        return self.headers.get("Host") in {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}

    def do_GET(self):
        if not self.host_ok():
            return self.reply(403, {"error": "Invalid host"})
        path = urlparse(self.path).path
        if path == "/api/config":
            return self.reply(200, {"workspace": str(self.app.workspace)})
        files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                 "/model.js": ("model.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if path not in files:
            return self.reply(404, {"error": "Not found"})
        name, mime = files[path]
        self.reply(200, (BASE / "static" / name).read_text(), mime + "; charset=utf-8")

    def do_POST(self):
        origin = self.headers.get("Origin")
        if (not self.host_ok() or self.headers.get("X-Mads-Lens") != "1" or
                (origin and origin not in {f"http://localhost:{self.server.server_port}", f"http://127.0.0.1:{self.server.server_port}"})):
            return self.reply(403, {"error": "Local same-origin requests only"})
        if self.path == "/api/stop":
            with self.app.lock:
                active = self.app.active
                if active:
                    active["stop"].set()
            return self.reply(200, {"stopped": bool(active)})
        if self.path != "/api/run":
            return self.reply(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 65536:
                raise ValueError("Request size must be 1–65536 bytes")
            body = json.loads(self.rfile.read(size))
            prompt, mode = body.get("prompt", ""), body.get("mode", "replay")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("프롬프트를 입력하세요.")
            if mode not in {"live", "replay", "failure"}:
                raise ValueError("Unknown mode")
            cwd = self.app.directory(body.get("cwd", "."))
            session = body.get("session_id")
            if session and self.app.sessions.get(session) != (str(cwd), mode):
                raise ValueError("새 세션을 시작하세요. 작업 폴더 또는 실행 모드가 다릅니다.")
        except (ValueError, TypeError, AttributeError, OSError) as exc:
            return self.reply(400, {"error": str(exc)})
        state = {"stop": threading.Event(), "process": None}
        with self.app.lock:
            if self.app.active:
                return self.reply(409, {"error": "실행 중인 작업을 먼저 종료하세요."})
            self.app.active = state
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.close_connection = True
        proc, archive = None, None
        finished = False
        deadline = time.monotonic() + self.app.timeout

        def emit(event):
            nonlocal finished
            if event.get("type") == "result":
                finished = True
            sid = event.get("session_id")
            if sid:
                self.app.sessions[sid] = (str(cwd), mode)
            data = (json.dumps(event, ensure_ascii=False) + "\n").encode()
            archive.write(data)
            archive.flush()
            self.wfile.write(data)
            self.wfile.flush()

        try:
            self.app.archive.mkdir(exist_ok=True)
            archive = (self.app.archive / f"{uuid.uuid4()}.jsonl").open("wb")
            emit({"type": "lens_start", "mode": mode, "prompt": prompt})
            if mode != "live":
                fixture = BASE / "fixtures" / ("failure.jsonl" if mode == "failure" else "tree.jsonl")
                for line in fixture.read_text().splitlines():
                    if state["stop"].wait(self.app.replay_delay):
                        raise RuntimeError("사용자가 실행을 중단했습니다.")
                    if time.monotonic() > deadline:
                        raise TimeoutError("실행 시간 제한을 초과했습니다.")
                    event = json.loads(line)
                    if event.get("session_id"):
                        event["session_id"] = session or "replay-session"
                    emit(event)
            else:
                env = dict(os.environ)
                # Course uses CLI login. Never silently fall back to personal API billing.
                env.pop("ANTHROPIC_API_KEY", None)
                proc = subprocess.Popen(self.app.command(prompt, session), cwd=cwd, env=env,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
                state["process"] = proc
                errors = bytearray()

                def drain_errors():
                    while chunk := proc.stderr.read(1024):
                        errors.extend(chunk)
                        del errors[:-8192]

                def watchdog():
                    while proc.poll() is None:
                        if state["stop"].wait(.1) or time.monotonic() > deadline:
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            return

                stderr_thread = threading.Thread(target=drain_errors, daemon=True)
                stderr_thread.start()
                threading.Thread(target=watchdog, daemon=True).start()
                for line in proc.stdout:
                    try:
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("Expected a JSON object")
                    except ValueError:
                        emit({"type": "lens_warning", "message": "JSON이 아닌 stdout 줄을 건너뛰었습니다."})
                        continue
                    emit(event)
                code = proc.wait()
                stderr_thread.join(timeout=1)
                if state["stop"].is_set():
                    raise RuntimeError("사용자가 실행을 중단했습니다.")
                if time.monotonic() > deadline:
                    raise TimeoutError("실행 시간 제한을 초과했습니다.")
                if code:
                    raise RuntimeError(f"Claude Code 종료 코드 {code}: {errors.decode(errors='replace')}")
            if not finished:
                raise RuntimeError("최종 result 이벤트 없이 스트림이 끝났습니다.")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            if archive:
                try:
                    emit({"type": "lens_error", "message": str(exc)})
                except (BrokenPipeError, ConnectionResetError):
                    pass
        finally:
            if proc and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            if proc:
                proc.stdout.close()
                proc.stderr.close()
            if archive:
                archive.close()
            with self.app.lock:
                self.app.active = None


def make_server(app, port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.app = app
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=BASE / "demo_project")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()
    server = make_server(App(args.workspace, timeout=args.timeout), args.port)
    print(f"Mads-Lens → http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with server.app.lock:
            if server.app.active:
                server.app.active["stop"].set()
        server.server_close()

"""The daemon: a local HTTP API in front of the Conductor, and a clock that ticks it."""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from conductor.core import Conductor

TICK_SECONDS = 2


def make_server(conductor: Conductor, port: int) -> ThreadingHTTPServer:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/status":
                return self._reply(404, {"error": f"no route {self.path}"})
            with lock:
                self._run(conductor.status)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            routes = {
                "/mood": lambda: conductor.request(
                    body["requester"],
                    body["mood"],
                    reason=body.get("reason", ""),
                    ttl=body.get("ttl"),
                ),
                "/release": lambda: conductor.release(body["requester"]),
                "/key": lambda: conductor.key(body["name"]),
            }
            if self.path not in routes:
                return self._reply(404, {"error": f"no route {self.path}"})
            with lock:
                self._run(routes[self.path])

        def _run(self, action):
            try:
                result = action()
            except (ValueError, KeyError) as e:
                return self._reply(400, {"error": str(e)})
            except (OSError, RuntimeError, LookupError) as e:  # the player is closed or refuses
                return self._reply(502, {"error": f"player: {e}"})
            self._reply(200, result if result is not None else {"ok": True})

        def _reply(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.lock = lock
    return server


def serve(conductor: Conductor, port: int) -> None:
    server = make_server(conductor, port)
    stop = threading.Event()

    def tick_forever():
        while not stop.wait(TICK_SECONDS):
            with server.lock:
                try:
                    conductor.tick()
                except Exception as e:  # noqa: BLE001 — one failed tick must not stop the clock
                    print(f"tick: {e}", file=sys.stderr)

    threading.Thread(target=tick_forever, daemon=True).start()
    print(f"conductor listening on 127.0.0.1:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    finally:
        stop.set()

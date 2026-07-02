"""Run a non-HTTP process with a minimal Railway health endpoint."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: process_supervisor.py <command> [args...]", file=sys.stderr)
        return 2

    child = subprocess.Popen(sys.argv[1:])

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            if self.path not in {"/health", "/health/"}:
                self.send_error(404)
                return
            running = child.poll() is None
            payload = json.dumps(
                {"status": "ok" if running else "error", "process_running": running}
            ).encode("utf-8")
            self.send_response(200 if running else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), HealthHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    def stop(_signum: int, _frame: object) -> None:
        if child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        return child.wait()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())

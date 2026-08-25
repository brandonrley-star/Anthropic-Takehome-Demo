#!/usr/bin/env python3
"""
Field Intelligence — local demo server.

Python standard library only, plus the `anthropic` SDK for the one optional
live Q&A endpoint. No build step, no framework, no new dependencies.

    python3 demo_ui/serve.py

Everything except /api/ask works with no API key and no network.
"""
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from demo_ui import data          # noqa: E402
from demo_ui import ask           # noqa: E402

STATIC = os.path.join(HERE, "static")
PORT = int(os.environ.get("PORT", "8000"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):        # quiet console during a recording
        pass

    # ------------------------------------------------------------- helpers
    def _send(self, body, ctype="application/json", status=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, rel):
        # Serve only from demo_ui/static. Nothing else on disk is reachable,
        # which also means eval/ can never be served by this process.
        path = os.path.normpath(os.path.join(STATIC, rel.lstrip("/")))
        if not path.startswith(STATIC) or not os.path.isfile(path):
            return self._send({"error": "not found"}, status=404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            self._send(f.read(), ctype)

    # ----------------------------------------------------------------- GET
    def do_GET(self):
        p = unquote(urlparse(self.path).path)
        try:
            if p in ("/", "/index.html"):
                return self._static("index.html")
            if p == "/api/overview":
                return self._send(data.overview())
            if p == "/api/provenance":
                return self._send(data.provenance())
            if p == "/api/baseline":
                return self._send(data.baseline_ranking())
            if p == "/api/findings":
                return self._send(data.findings_list())
            if p.startswith("/api/finding/"):
                d = data.finding_detail(p.rsplit("/", 1)[-1])
                return self._send(d or {"error": "unknown finding"},
                                  status=200 if d else 404)
            if p.startswith("/api/work_order/"):
                w = data.work_order(p.rsplit("/", 1)[-1])
                return self._send(w or {"error": "unknown work order"},
                                  status=200 if w else 404)
            if p == "/api/ask/status":
                return self._send(ask.status())
            if p.startswith("/static/"):
                return self._static(p[len("/static/"):])
            return self._static(p)
        except Exception as e:                                  # never 500 blank
            return self._send({"error": f"{type(e).__name__}: {e}"}, status=500)

    def _stream_ask(self):
        """Server-sent events. Each delta is one `data:` line of JSON."""
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send({"error": "bad request"}, status=400)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(obj):
            try:
                self.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                raise
        try:
            tail = ask.stream(req.get("candidate_id", ""), req.get("question", ""),
                              lambda t: emit({"delta": t}))
            emit(tail)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            try:
                emit({"error": f"{type(e).__name__}: {e}"})
            except Exception:
                pass
        self.close_connection = True

    # ---------------------------------------------------------------- POST
    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/ask/stream":
            return self._stream_ask()
        if p != "/api/ask":
            return self._send({"error": "not found"}, status=404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            out = ask.answer(req.get("candidate_id", ""), req.get("question", ""))
            return self._send(out, status=200 if "error" not in out else 400)
        except Exception as e:
            return self._send({"error": f"{type(e).__name__}: {e}"}, status=500)


def _noop():
    pass


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    st = ask.status()
    print("\n  Field Intelligence")
    print(f"  {url}")
    print(f"  Live Claude Q&A: {'enabled (' + st['model'] + ')' if st['available'] else 'disabled — no API key'}")
    print("  Ctrl-C to stop\n")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped\n")


if __name__ == "__main__":
    main()

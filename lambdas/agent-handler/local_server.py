"""Local dev server that exposes the real /query handler over HTTP.

For frontend testing without Docker/SAM: it reuses handler.handler and runs TTS
locally via the tts-handler code (like cli.py), so the Next.js app can point
NEXT_PUBLIC_API_URL at it. Config comes from the repo-root .env.

Run (from lambdas/agent-handler, using its venv):
    .venv/Scripts/python local_server.py            # serves on :8000
    .venv/Scripts/python local_server.py --port 3001

Then set frontend/.env.local:
    NEXT_PUBLIC_API_URL=http://localhost:8000/query
"""

import argparse
import importlib.util
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

_HERE = Path(__file__).resolve().parent
_TTS_HANDLER_PATH = _HERE.parent / "tts-handler" / "handler.py"

_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def _load_tts_synthesize():
    spec = importlib.util.spec_from_file_location("tts_local", _TTS_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return lambda text, lang: module.handler({"text": text, "lang": lang}).get(
        "audio_b64", ""
    )


def _build_handler_module():
    load_dotenv(find_dotenv(usecwd=False))
    for key in ("OWM_API_KEY", "LLM_MODEL_ID", "LLM_BASE_URL", "LLM_API_KEY"):
        if not os.environ.get(key):
            raise SystemExit(f"{key} is not set (add it to the repo-root .env).")
    os.environ.setdefault("TTS_LAMBDA_NAME", "local-tts")
    os.environ.setdefault("AWS_REGION", "us-east-1")

    import handler

    handler._synthesize = _load_tts_synthesize()
    return handler


def make_request_handler(handler_module):
    class QueryHandler(BaseHTTPRequestHandler):
        def _send(self, status, body_text, extra_headers=None):
            self.send_response(status)
            for key, value in {**_CORS, **(extra_headers or {})}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body_text.encode("utf-8"))

        def do_OPTIONS(self):  # CORS preflight
            self._send(204, "")

        def do_POST(self):
            if self.path.rstrip("/") not in ("/query", ""):
                self._send(404, '{"error": "not found"}',
                           {"Content-Type": "application/json"})
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            result = handler_module.handler({"body": raw})
            self._send(
                result["statusCode"], result["body"],
                {"Content-Type": "application/json"},
            )

        def log_message(self, fmt, *args):
            print(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    return QueryHandler


def main():
    parser = argparse.ArgumentParser(description="Local /query dev server")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    handler_module = _build_handler_module()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_request_handler(handler_module))
    print(f"Serving /query on http://localhost:{args.port}/query  (model={os.environ.get('LLM_MODEL_ID')})")
    print("Set frontend/.env.local: "
          f"NEXT_PUBLIC_API_URL=http://localhost:{args.port}/query")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping.")


if __name__ == "__main__":
    main()

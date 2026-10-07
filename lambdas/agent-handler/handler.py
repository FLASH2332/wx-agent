"""AWS Lambda adapter. All behaviour lives in `agent_service`; this only maps the
Lambda event (API Gateway REST or Function URL) to a service call and back.

CORS is intentionally not set here: the Function URL / API Gateway configuration in
template.yaml adds it (setting it in both places produces duplicate headers).
"""

import base64
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# Deployed: agent_service sits next to this file. Local checkout: it is in the repo root.
for _path in (_HERE, os.path.abspath(os.path.join(_HERE, "..", ".."))):
    if _path not in sys.path:
        sys.path.append(_path)

from agent_service import service  # noqa: E402

_JSON = {"Content-Type": "application/json"}


def _reply(status, body):
    return {"statusCode": status, "headers": _JSON, "body": json.dumps(body)}


def _body(event):
    raw = event.get("body")
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def handler(event, context=None):
    # rawPath: Function URL; path: API Gateway REST.
    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "POST").upper()

    if method == "GET" and path.endswith("/health"):
        return _reply(*service.handle_health())
    try:
        body = _body(event)
    except (ValueError, UnicodeDecodeError):
        return _reply(400, {"error": "Invalid JSON body", "code": "invalid_json"})

    routes = {
        "/transcribe": service.handle_transcribe,
        "/sync": service.handle_sync,
        "/tts": service.handle_tts,
    }
    for suffix, fn in routes.items():
        if path.endswith(suffix):
            return _reply(*fn(body))
    return _reply(*service.handle_query(body))

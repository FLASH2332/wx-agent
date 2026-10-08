"""Starlette HTTP app: the local server today, the container entrypoint later.

Run:  python -m agent_service
      (or: uvicorn agent_service.api:create_app --factory --port 3001)
"""

from __future__ import annotations

import logging

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from . import service
from .config import get_settings, load_dotenv_file


async def _json_body(request: Request):
    try:
        return await request.json()
    except ValueError:
        return None


def _post(handler):
    async def endpoint(request: Request) -> JSONResponse:
        body = await _json_body(request)
        if body is None:
            return JSONResponse({"error": "Invalid JSON body", "code": "invalid_json"}, status_code=400)
        status, payload = await run_in_threadpool(handler, body)
        return JSONResponse(payload, status_code=status)
    return endpoint


async def health(request: Request) -> JSONResponse:
    status, payload = await run_in_threadpool(service.handle_health)
    return JSONResponse(payload, status_code=status)


async def diag_aws(request: Request) -> JSONResponse:
    status, payload = await run_in_threadpool(service.handle_diag)
    return JSONResponse(payload, status_code=status)


def create_app(load_env: bool = True) -> Starlette:
    if load_env:
        load_dotenv_file()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/diag/aws", diag_aws, methods=["GET"]),
            Route("/query", _post(service.handle_query), methods=["POST"]),
            Route("/transcribe", _post(service.handle_transcribe), methods=["POST"]),
            Route("/sync", _post(service.handle_sync), methods=["POST"]),
            Route("/tts", _post(service.handle_tts), methods=["POST"]),
        ],
        middleware=[Middleware(
            CORSMiddleware, allow_origins=list(settings.cors_allow_origins),
            allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])],
    )

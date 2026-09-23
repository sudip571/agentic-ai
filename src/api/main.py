from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from src.api.dependencies import get_database
from src.api.routes.chat import router as chat_router
from src.api.routes.demo import router as demo_router
from src.api.routes.health import router as health_router
from src.shared.configuration import get_settings
from src.shared.errors import (
    AppError,
    AuthorizationException,
    ConflictException,
    ExternalServiceException,
    NotFoundException,
    ValidationException,
)
from src.shared.logging import configure_logging
from src.shared.observability import record_http_request


def _extract_trace_id(request: Request) -> str:
    x_trace_id = request.headers.get("X-Trace-Id")
    if x_trace_id:
        return x_trace_id
    traceparent = request.headers.get("traceparent")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 4 and len(parts[1]) == 32:
            return parts[1]
    return uuid4().hex


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    database = get_database()
    settings = get_settings()
    if settings.environment in {"development", "test"}:
        await database.create_schema()
    yield


app = FastAPI(title="Billing Agent", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(demo_router)


@app.middleware("http")
async def apply_security_and_request_limits(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    settings = get_settings()
    trace_id = _extract_trace_id(request)
    request.state.trace_id = trace_id
    bind_contextvars(trace_id=trace_id)

    start = perf_counter()
    status_code = 500
    if request.method == "POST" and request.url.path == "/api/chat":
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > settings.max_request_body_bytes:
            response: Response = JSONResponse(
                {"detail": "Request body too large"},
                status_code=413,
            )
            response.headers["X-Trace-Id"] = trace_id
            status_code = response.status_code
            duration_seconds = perf_counter() - start
            record_http_request(request.method, request.url.path, status_code, duration_seconds)
            clear_contextvars()
            return response

    try:
        response = await call_next(request)
        status_code = response.status_code
    finally:
        duration_seconds = perf_counter() - start
        record_http_request(request.method, request.url.path, status_code, duration_seconds)
        clear_contextvars()

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if request.url.path.startswith("/internal/demo"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status = 500
    if isinstance(exc, ValidationException):
        status = 400
    elif isinstance(exc, AuthorizationException):
        status = 403
    elif isinstance(exc, NotFoundException):
        status = 404
    elif isinstance(exc, ConflictException):
        status = 409
    elif isinstance(exc, ExternalServiceException):
        status = 503
    trace_id = getattr(request.state, "trace_id", "")
    payload: dict[str, str] = {"detail": str(exc)}
    if trace_id:
        payload["trace_id"] = trace_id
    return JSONResponse(payload, status_code=status)

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import Header, HTTPException, status

from src.shared.configuration import get_settings

_limiter_lock = Lock()
_request_windows: dict[str, deque[datetime]] = defaultdict(deque)


def _check_rate_limit(key: str) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    window = timedelta(seconds=settings.api_rate_limit_window_seconds)

    with _limiter_lock:
        timestamps = _request_windows[key]
        while timestamps and now - timestamps[0] > window:
            timestamps.popleft()

        if len(timestamps) >= settings.api_rate_limit_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        timestamps.append(now)


async def rate_limit_chat(
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> None:
    key = x_api_key or "anonymous"
    _check_rate_limit(f"chat:{key}")


async def rate_limit_approval(
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> None:
    key = x_api_key or "anonymous"
    _check_rate_limit(f"approval:{key}")

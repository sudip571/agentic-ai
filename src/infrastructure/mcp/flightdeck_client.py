from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

import httpx

from mcp_server.services.flightdeck_service import MCPFlightdeckService
from src.shared.configuration import Settings
from src.shared.errors import ExternalServiceException
from src.shared.logging import get_logger
from src.shared.observability import record_mcp_result


class FlightdeckMCPClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._logger = get_logger(__name__)
        self._settings = settings
        self._transport = transport
        self._service = MCPFlightdeckService() if settings.mcp_client_mode == "local" else None
        self._base_url = self._normalized_base_url(settings.mcp_server_url)
        self._consecutive_failures = 0
        self._circuit_open_until: datetime | None = None

    async def get_report_capabilities(self, role: str | None) -> dict[str, Any]:
        return await self._invoke_tool("fd_get_report_capabilities", {"role": role})

    async def get_guidance_steps(self, report_type: str) -> dict[str, Any]:
        return await self._invoke_tool("fd_get_guidance_steps", {"report_type": report_type})

    async def get_share_of_voice_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._invoke_tool("fd_get_share_of_voice_report", payload)

    async def _invoke_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            if self._settings.mcp_client_mode == "local":
                result = self._invoke_local(tool_name, payload)
                record_mcp_result(tool_name, "success", perf_counter() - started_at)
                return result

            result = await self._invoke_http(tool_name, payload)
            record_mcp_result(tool_name, "success", perf_counter() - started_at)
            return result
        except Exception:
            record_mcp_result(tool_name, "failure", perf_counter() - started_at)
            raise

    def _invoke_local(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._service is None:
            raise ExternalServiceException("Flightdeck MCP local service not configured")

        if tool_name == "fd_get_report_capabilities":
            return self._service.get_report_capabilities(payload.get("role"))
        if tool_name == "fd_get_guidance_steps":
            return self._service.get_guidance_steps(payload["report_type"])
        if tool_name == "fd_get_share_of_voice_report":
            return self._service.get_share_of_voice_report(
                tenant_id=payload.get("tenant_id"),
                account_id=payload["account_id"],
                start_date=payload["start_date"],
                end_date=payload["end_date"],
                timezone=payload["timezone"],
                market=payload.get("market"),
                channel=payload.get("channel"),
                brand=payload.get("brand"),
            )
        raise ExternalServiceException(f"Unsupported Flightdeck MCP tool: {tool_name}")

    async def _invoke_http(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_circuit_closed(tool_name)
        path_map = {
            "fd_get_report_capabilities": "/tools/fd/get_report_capabilities",
            "fd_get_guidance_steps": "/tools/fd/get_guidance_steps",
            "fd_get_share_of_voice_report": "/tools/fd/get_share_of_voice_report",
        }
        endpoint = path_map.get(tool_name)
        if endpoint is None:
            raise ExternalServiceException(f"Unsupported Flightdeck MCP tool: {tool_name}")

        url = f"{self._base_url}{endpoint}"
        headers = {"X-MCP-Token": self._settings.mcp_service_token}
        attempts = max(1, self._settings.mcp_retry_attempts)
        last_error: ExternalServiceException | None = None

        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(
                    transport=self._transport,
                    timeout=self._settings.mcp_timeout_seconds,
                ) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code >= 500 or response.status_code == 429:
                        raise httpx.HTTPStatusError(
                            f"Retryable MCP status: {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ExternalServiceException("MCP response is not an object")
                    self._record_success()
                    return data
            except httpx.TimeoutException:
                last_error = ExternalServiceException("Flightdeck MCP request timed out")
                if attempt < attempts:
                    await self._retry_backoff(tool_name, attempt, "timeout")
                    continue
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code >= 500 or status_code == 429
                last_error = ExternalServiceException(f"Flightdeck MCP failed: HTTP {status_code}")
                if retryable and attempt < attempts:
                    await self._retry_backoff(tool_name, attempt, f"http_{status_code}")
                    continue
            except httpx.HTTPError as exc:
                last_error = ExternalServiceException(f"Flightdeck MCP transport error: {exc}")
                if attempt < attempts:
                    await self._retry_backoff(tool_name, attempt, "transport")
                    continue
            break

        self._record_failure(tool_name)
        if last_error is None:
            raise ExternalServiceException("Flightdeck MCP request failed")
        raise last_error

    def _normalized_base_url(self, configured_url: str) -> str:
        trimmed = configured_url.rstrip("/")
        if trimmed.endswith("/mcp"):
            return trimmed[: -len("/mcp")]
        return trimmed

    def _ensure_circuit_closed(self, tool_name: str) -> None:
        if self._circuit_open_until is None:
            return
        now = datetime.now(UTC)
        if now >= self._circuit_open_until:
            self._circuit_open_until = None
            self._consecutive_failures = 0
            return
        self._logger.warning(
            "flightdeck_mcp_circuit_open",
            tool_name=tool_name,
            open_until=self._circuit_open_until.isoformat(),
        )
        raise ExternalServiceException("Flightdeck MCP circuit breaker is open")

    async def _retry_backoff(self, tool_name: str, attempt: int, reason: str) -> None:
        delay = self._settings.mcp_retry_backoff_seconds * attempt
        self._logger.warning(
            "flightdeck_mcp_retry_scheduled",
            tool_name=tool_name,
            attempt=attempt,
            delay_seconds=delay,
            reason=reason,
        )
        if delay > 0:
            await asyncio.sleep(delay)

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = None

    def _record_failure(self, tool_name: str) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._settings.mcp_circuit_breaker_threshold:
            return
        self._circuit_open_until = datetime.now(UTC) + timedelta(
            seconds=self._settings.mcp_circuit_breaker_cooldown_seconds
        )
        self._logger.error(
            "flightdeck_mcp_circuit_opened",
            tool_name=tool_name,
            consecutive_failures=self._consecutive_failures,
            open_until=self._circuit_open_until.isoformat(),
        )

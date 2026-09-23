from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any

import httpx
from pydantic import BaseModel

from mcp_server.services.billing_service import MCPBillingService
from src.domain.models.contract import Contract
from src.domain.models.customer import Customer
from src.domain.models.invoice import Invoice
from src.shared.configuration import Settings
from src.shared.errors import ExternalServiceException
from src.shared.logging import get_logger
from src.shared.observability import record_mcp_result


@dataclass(frozen=True)
class MCPToolMetadata:
    name: str
    classification: str
    requires_permission: str


TOOL_CLASSIFICATION = {
    "get_customer": MCPToolMetadata("get_customer", "READ_ONLY", "READ"),
    "get_contract": MCPToolMetadata("get_contract", "READ_ONLY", "READ"),
    "get_invoice": MCPToolMetadata("get_invoice", "READ_ONLY", "READ"),
    "create_credit": MCPToolMetadata("create_credit", "WRITE", "WRITE"),
    "request_approval": MCPToolMetadata("request_approval", "WRITE", "WRITE"),
}


class MCPCustomerResult(BaseModel):
    customer_id: str
    email: str
    status: str


class MCPContractResult(BaseModel):
    contract_id: str
    customer_id: str
    monthly_price: str
    currency: str
    effective_from: datetime
    effective_to: datetime | None
    status: str


class MCPInvoiceResult(BaseModel):
    invoice_id: str
    customer_id: str
    billing_period: str
    issued_at: datetime
    total: str
    currency: str
    status: str


class MCPCreditResult(BaseModel):
    credit_id: str
    customer_id: str
    invoice_id: str
    amount: str
    reason: str
    status: str


class MCPApprovalResult(BaseModel):
    approval_id: str
    customer_id: str
    invoice_id: str
    amount: str
    status: str


class BillingMCPClient:
    """Typed adapter over MCP capabilities used by the billing workflow."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._logger = get_logger(__name__)
        self._settings = settings
        self._transport = transport
        self._service = MCPBillingService(settings) if settings.mcp_client_mode == "local" else None
        self._base_url = self._normalized_base_url(settings.mcp_server_url)
        self._consecutive_failures = 0
        self._circuit_open_until: datetime | None = None

    async def get_customer(self, customer_id: str) -> Customer:
        payload = await self._invoke_tool("get_customer", {"customer_id": customer_id})
        parsed = MCPCustomerResult.model_validate(payload)
        return Customer(id=parsed.customer_id, email=parsed.email, status=parsed.status)

    async def get_contract(self, customer_id: str, issued_at: datetime) -> Contract:
        payload = await self._invoke_tool(
            "get_contract",
            {"customer_id": customer_id, "issued_at": issued_at.isoformat()},
        )
        parsed = MCPContractResult.model_validate(payload)
        return Contract(
            id=parsed.contract_id,
            customer_id=parsed.customer_id,
            monthly_price={"amount": Decimal(parsed.monthly_price), "currency": parsed.currency},
            effective_from=parsed.effective_from,
            effective_to=parsed.effective_to,
            status=parsed.status,
        )

    async def get_invoice(self, customer_id: str) -> Invoice:
        payload = await self._invoke_tool("get_invoice", {"customer_id": customer_id})
        parsed = MCPInvoiceResult.model_validate(payload)
        return Invoice(
            id=parsed.invoice_id,
            customer_id=parsed.customer_id,
            billing_period=parsed.billing_period,
            issued_at=parsed.issued_at,
            total={"amount": Decimal(parsed.total), "currency": parsed.currency},
            status=parsed.status,
        )

    async def create_credit(
        self,
        customer_id: str,
        invoice_id: str,
        amount: Decimal,
        reason: str,
    ) -> str:
        payload = await self._invoke_tool(
            "create_credit",
            {
                "customer_id": customer_id,
                "invoice_id": invoice_id,
                "amount": str(amount),
                "reason": reason,
            },
        )
        parsed = MCPCreditResult.model_validate(payload)
        return parsed.credit_id

    async def request_approval(
        self,
        customer_id: str,
        invoice_id: str,
        amount: Decimal,
    ) -> str:
        payload = await self._invoke_tool(
            "request_approval",
            {
                "customer_id": customer_id,
                "invoice_id": invoice_id,
                "amount": str(amount),
            },
        )
        parsed = MCPApprovalResult.model_validate(payload)
        return parsed.approval_id

    async def _with_timeout(self, awaitable: Any) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(awaitable, timeout=self._settings.mcp_timeout_seconds)
        except TimeoutError as exc:
            raise ExternalServiceException("MCP request timed out") from exc
        except Exception as exc:
            message = f"MCP request failed: {exc}"
            raise ExternalServiceException(message) from exc

    async def _invoke_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            if self._settings.mcp_client_mode == "local":
                if self._service is None:
                    raise ExternalServiceException("MCP local service not configured")
                if tool_name == "get_customer":
                    result = await self._with_timeout(
                        self._service.get_customer(payload["customer_id"])
                    )
                    record_mcp_result(tool_name, "success", perf_counter() - started_at)
                    return result
                if tool_name == "get_contract":
                    issued_at = datetime.fromisoformat(payload["issued_at"])
                    result = await self._with_timeout(
                        self._service.get_contract(payload["customer_id"], issued_at)
                    )
                    record_mcp_result(tool_name, "success", perf_counter() - started_at)
                    return result
                if tool_name == "get_invoice":
                    result = await self._with_timeout(
                        self._service.get_invoice(payload["customer_id"])
                    )
                    record_mcp_result(tool_name, "success", perf_counter() - started_at)
                    return result
                if tool_name == "create_credit":
                    result = await self._with_timeout(
                        self._service.create_credit(
                            payload["customer_id"],
                            payload["invoice_id"],
                            payload["amount"],
                            payload["reason"],
                        )
                    )
                    record_mcp_result(tool_name, "success", perf_counter() - started_at)
                    return result
                if tool_name == "request_approval":
                    result = await self._with_timeout(
                        self._service.request_approval(
                            payload["customer_id"],
                            payload["invoice_id"],
                            payload["amount"],
                        )
                    )
                    record_mcp_result(tool_name, "success", perf_counter() - started_at)
                    return result
                raise ExternalServiceException(f"Unsupported local MCP tool: {tool_name}")

            result = await self._invoke_http_tool(tool_name, payload)
            record_mcp_result(tool_name, "success", perf_counter() - started_at)
            return result
        except Exception:
            record_mcp_result(tool_name, "failure", perf_counter() - started_at)
            raise

    async def _invoke_http_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_circuit_closed(tool_name)

        url = f"{self._base_url}/tools/{tool_name}"
        headers = {"X-MCP-Token": self._settings.mcp_service_token}
        last_error: ExternalServiceException | None = None

        attempts = max(1, self._settings.mcp_retry_attempts)
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
                last_error = ExternalServiceException("MCP request timed out")
                if attempt < attempts:
                    await self._retry_backoff(tool_name, attempt, "timeout")
                    continue
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code >= 500 or status_code == 429
                message = f"MCP request failed: HTTP {status_code}"
                last_error = ExternalServiceException(message)
                if retryable and attempt < attempts:
                    await self._retry_backoff(tool_name, attempt, f"http_{status_code}")
                    continue
            except httpx.HTTPError as exc:
                message = f"MCP transport error: {exc}"
                last_error = ExternalServiceException(message)
                if attempt < attempts:
                    await self._retry_backoff(tool_name, attempt, "transport")
                    continue

            break

        self._record_failure(tool_name)
        if last_error is None:
            raise ExternalServiceException("MCP request failed")
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
            "mcp_circuit_open",
            tool_name=tool_name,
            open_until=self._circuit_open_until.isoformat(),
        )
        raise ExternalServiceException("MCP circuit breaker is open")

    async def _retry_backoff(self, tool_name: str, attempt: int, reason: str) -> None:
        delay = self._settings.mcp_retry_backoff_seconds * attempt
        self._logger.warning(
            "mcp_retry_scheduled",
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
        now = datetime.now(UTC)
        self._circuit_open_until = now + timedelta(
            seconds=self._settings.mcp_circuit_breaker_cooldown_seconds
        )
        self._logger.error(
            "mcp_circuit_opened",
            tool_name=tool_name,
            consecutive_failures=self._consecutive_failures,
            open_until=self._circuit_open_until.isoformat(),
        )

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from src.infrastructure.mcp.client import BillingMCPClient
from src.shared.configuration import Settings
from src.shared.errors import ExternalServiceException


def _transport() -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("X-MCP-Token") != "test-mcp-token":
            return httpx.Response(401, json={"detail": "Unauthorized"})

        if request.url.path == "/tools/get_customer":
            return httpx.Response(
                200,
                json={
                    "customer_id": "CUST-001",
                    "email": "cust001@example.com",
                    "status": "ACTIVE",
                },
            )
        if request.url.path == "/tools/get_invoice":
            return httpx.Response(
                200,
                json={
                    "invoice_id": "INV-001",
                    "customer_id": "CUST-001",
                    "billing_period": "2026-09",
                    "issued_at": datetime.now(UTC).isoformat(),
                    "total": "150.00",
                    "currency": "USD",
                    "status": "FINALIZED",
                },
            )
        if request.url.path == "/tools/get_contract":
            return httpx.Response(
                200,
                json={
                    "contract_id": "CONT-001",
                    "customer_id": "CUST-001",
                    "monthly_price": "100.00",
                    "currency": "USD",
                    "effective_from": datetime.now(UTC).isoformat(),
                    "effective_to": None,
                    "status": "ACTIVE",
                },
            )
        if request.url.path == "/tools/create_credit":
            return httpx.Response(
                200,
                json={
                    "credit_id": "CRD-001",
                    "customer_id": "CUST-001",
                    "invoice_id": "INV-001",
                    "amount": "50.00",
                    "reason": "Billing discrepancy auto-correction",
                    "status": "created",
                },
            )
        if request.url.path == "/tools/request_approval":
            return httpx.Response(
                200,
                json={
                    "approval_id": "APR-001",
                    "customer_id": "CUST-001",
                    "invoice_id": "INV-001",
                    "amount": "50.00",
                    "status": "pending",
                },
            )
        return httpx.Response(404, json={"detail": "Not Found"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_http_mode_fetches_customer_contract_invoice() -> None:
    settings = Settings(
        mcp_client_mode="http",
        mcp_server_url="http://mcp.test",
        mcp_service_token="test-mcp-token",
    )
    client = BillingMCPClient(settings, transport=_transport())

    customer = await client.get_customer("CUST-001")
    invoice = await client.get_invoice("CUST-001")
    contract = await client.get_contract("CUST-001", invoice.issued_at)
    credit_id = await client.create_credit(
        customer_id="CUST-001",
        invoice_id="INV-001",
        amount=contract.monthly_price.amount,
        reason="Billing discrepancy auto-correction",
    )
    approval_id = await client.request_approval(
        customer_id="CUST-001",
        invoice_id="INV-001",
        amount=contract.monthly_price.amount,
    )

    assert customer.id == "CUST-001"
    assert invoice.id == "INV-001"
    assert contract.id == "CONT-001"
    assert credit_id == "CRD-001"
    assert approval_id == "APR-001"


@pytest.mark.asyncio
async def test_http_mode_maps_status_errors() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "down"})

    settings = Settings(
        mcp_client_mode="http",
        mcp_server_url="http://mcp.test",
        mcp_service_token="test-mcp-token",
    )
    client = BillingMCPClient(settings, transport=httpx.MockTransport(handler))

    with pytest.raises(ExternalServiceException):
        await client.get_customer("CUST-001")


@pytest.mark.asyncio
async def test_http_mode_rejects_when_token_is_invalid() -> None:
    settings = Settings(
        mcp_client_mode="http",
        mcp_server_url="http://mcp.test",
        mcp_service_token="wrong-token",
    )
    client = BillingMCPClient(settings, transport=_transport())

    with pytest.raises(ExternalServiceException):
        await client.get_customer("CUST-001")


@pytest.mark.asyncio
async def test_http_mode_retries_retryable_failures_then_succeeds() -> None:
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if request.headers.get("X-MCP-Token") != "test-mcp-token":
            return httpx.Response(401, json={"detail": "Unauthorized"})
        if attempts["count"] < 3:
            return httpx.Response(503, json={"detail": "temporary failure"})
        return httpx.Response(
            200,
            json={
                "credit_id": "CRD-RETRY-001",
                "customer_id": "CUST-001",
                "invoice_id": "INV-001",
                "amount": "25.00",
                "reason": "retry test",
                "status": "created",
            },
        )

    settings = Settings(
        mcp_client_mode="http",
        mcp_server_url="http://mcp.test",
        mcp_service_token="test-mcp-token",
        mcp_retry_attempts=3,
        mcp_retry_backoff_seconds=0,
        mcp_circuit_breaker_threshold=5,
    )
    client = BillingMCPClient(settings, transport=httpx.MockTransport(handler))

    credit_id = await client.create_credit(
        customer_id="CUST-001",
        invoice_id="INV-001",
        amount=Decimal("25.00"),
        reason="retry test",
    )

    assert credit_id == "CRD-RETRY-001"
    assert attempts["count"] == 3


@pytest.mark.asyncio
async def test_http_mode_circuit_breaker_fails_fast_after_threshold() -> None:
    attempts = {"count": 0}

    async def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"detail": "down"})

    settings = Settings(
        mcp_client_mode="http",
        mcp_server_url="http://mcp.test",
        mcp_service_token="test-mcp-token",
        mcp_retry_attempts=1,
        mcp_retry_backoff_seconds=0,
        mcp_circuit_breaker_threshold=2,
        mcp_circuit_breaker_cooldown_seconds=60,
    )
    client = BillingMCPClient(settings, transport=httpx.MockTransport(handler))

    with pytest.raises(ExternalServiceException):
        await client.get_customer("CUST-001")
    with pytest.raises(ExternalServiceException):
        await client.get_customer("CUST-001")

    # Third call should fail fast from open circuit and avoid a transport call.
    with pytest.raises(ExternalServiceException):
        await client.get_customer("CUST-001")

    assert attempts["count"] == 2

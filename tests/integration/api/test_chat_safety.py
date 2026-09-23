from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.api.dependencies import get_billing_service, get_llm_client
from src.api.main import app
from src.application.services.billing_service import BillingService
from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.models import ApprovalRequestTable, CreditTable
from src.infrastructure.persistence.seed import seed
from src.shared.configuration import get_settings
from src.shared.errors import ExternalServiceException


@dataclass
class _Parsed:
    claimed_amount: None = None
    expected_amount: None = None
    requested_action: str = "investigate"


class _FakeLLMClient:
    async def parse_request(self, _: str) -> _Parsed:
        return _Parsed()


class _CircuitOpenMCPClient:
    def __init__(self) -> None:
        self.create_credit_calls = 0
        self.request_approval_calls = 0

    async def get_customer(self, customer_id: str) -> Any:
        raise ExternalServiceException("MCP circuit breaker is open")

    async def get_invoice(self, customer_id: str) -> Any:
        raise AssertionError("get_invoice should not be called when get_customer fails")

    async def get_contract(self, customer_id: str, issued_at: datetime) -> Any:
        raise AssertionError("get_contract should not be called when get_customer fails")

    async def create_credit(
        self,
        customer_id: str,
        invoice_id: str,
        amount: Decimal,
        reason: str,
    ) -> str:
        self.create_credit_calls += 1
        return "UNEXPECTED"

    async def request_approval(
        self,
        customer_id: str,
        invoice_id: str,
        amount: Decimal,
    ) -> str:
        self.request_approval_calls += 1
        return "UNEXPECTED"


def _count_credits() -> int:
    async def _run() -> int:
        db = Database(get_settings())
        async for session in db.get_session():
            count = await session.scalar(select(func.count()).select_from(CreditTable))
            return int(count or 0)
        return 0

    return asyncio.run(_run())


def _count_approvals() -> int:
    async def _run() -> int:
        db = Database(get_settings())
        async for session in db.get_session():
            count = await session.scalar(select(func.count()).select_from(ApprovalRequestTable))
            return int(count or 0)
        return 0

    return asyncio.run(_run())


def test_chat_returns_safe_failure_when_mcp_circuit_is_open() -> None:
    asyncio.run(seed())
    settings = get_settings()
    fake_mcp = _CircuitOpenMCPClient()
    service = BillingService(settings=settings, mcp_client=cast(Any, fake_mcp))

    app.dependency_overrides[get_billing_service] = lambda: service
    app.dependency_overrides[get_llm_client] = lambda: _FakeLLMClient()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
                json={
                    "message": "My bill is 150 and should be 100",
                    "customer_id": "CUST-001",
                    "request_id": "REQ-CIRCUIT-001",
                },
            )

        assert response.status_code == 503
        assert response.json()["detail"] == "MCP circuit breaker is open"
        assert fake_mcp.create_credit_calls == 0
        assert fake_mcp.request_approval_calls == 0
    finally:
        app.dependency_overrides.clear()


def test_chat_prevents_duplicate_credit_side_effects_for_same_request_id() -> None:
    asyncio.run(seed())
    settings = get_settings()
    request_id = f"REQ-DEDUP-{uuid4()}"

    app.dependency_overrides[get_llm_client] = lambda: _FakeLLMClient()
    before_credit_count = _count_credits()
    before_approval_count = _count_approvals()

    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/chat",
                headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
                json={
                    "message": "My bill is $150 but should be $100",
                    "customer_id": "CUST-001",
                    "request_id": request_id,
                },
            )
            second = client.post(
                "/api/chat",
                headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
                json={
                    "message": "My bill is $150 but should be $100",
                    "customer_id": "CUST-001",
                    "request_id": request_id,
                },
            )

        after_credit_count = _count_credits()
        after_approval_count = _count_approvals()

        assert first.status_code == 200
        assert second.status_code == 409
        assert first.json()["requires_human_approval"] is True
        assert after_credit_count - before_credit_count == 0
        assert after_approval_count - before_approval_count == 1
    finally:
        app.dependency_overrides.clear()

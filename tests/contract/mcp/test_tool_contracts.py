from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mcp_server.services.billing_service import MCPBillingService
from src.infrastructure.mcp.client import TOOL_CLASSIFICATION
from src.infrastructure.persistence.seed import seed


@pytest.mark.asyncio
async def test_mcp_read_tools_are_classified() -> None:
    assert TOOL_CLASSIFICATION["get_customer"].classification == "READ_ONLY"
    assert TOOL_CLASSIFICATION["get_contract"].classification == "READ_ONLY"
    assert TOOL_CLASSIFICATION["get_invoice"].classification == "READ_ONLY"


@pytest.mark.asyncio
async def test_mcp_write_tools_are_classified() -> None:
    assert TOOL_CLASSIFICATION["create_credit"].classification == "WRITE"
    assert TOOL_CLASSIFICATION["request_approval"].classification == "WRITE"


@pytest.mark.asyncio
async def test_mcp_service_customer_contract_invoice_payloads() -> None:
    await seed()
    service = MCPBillingService()

    customer = await service.get_customer("CUST-001")
    assert set(customer.keys()) == {"customer_id", "email", "status"}
    assert customer["customer_id"] == "CUST-001"

    invoice = await service.get_invoice("CUST-001")
    assert set(invoice.keys()) == {
        "invoice_id",
        "customer_id",
        "billing_period",
        "issued_at",
        "total",
        "currency",
        "status",
    }
    assert invoice["customer_id"] == "CUST-001"

    contract = await service.get_contract("CUST-001", datetime.now(UTC))
    assert set(contract.keys()) == {
        "contract_id",
        "customer_id",
        "monthly_price",
        "currency",
        "effective_from",
        "effective_to",
        "status",
    }
    assert contract["customer_id"] == "CUST-001"

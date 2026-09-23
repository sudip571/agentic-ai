from __future__ import annotations

from mcp_server.services.billing_service import MCPBillingService


async def create_credit_tool(
    service: MCPBillingService,
    customer_id: str,
    invoice_id: str,
    amount: str,
    reason: str,
) -> dict[str, str]:
    return await service.create_credit(customer_id, invoice_id, amount, reason)


async def request_approval_tool(
    service: MCPBillingService,
    customer_id: str,
    invoice_id: str,
    amount: str,
) -> dict[str, str]:
    return await service.request_approval(customer_id, invoice_id, amount)

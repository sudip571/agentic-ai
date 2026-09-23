from __future__ import annotations

from mcp_server.services.billing_service import MCPBillingService


async def get_customer_tool(service: MCPBillingService, customer_id: str) -> dict[str, str]:
    return await service.get_customer(customer_id)

from __future__ import annotations

from datetime import datetime

from mcp_server.services.billing_service import MCPBillingService


async def get_contract_tool(
    service: MCPBillingService,
    customer_id: str,
    issued_at: datetime | None = None,
) -> dict[str, str | None]:
    return await service.get_contract(customer_id, issued_at)

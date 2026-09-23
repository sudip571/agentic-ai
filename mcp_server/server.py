# mypy: disable-error-code=untyped-decorator
from __future__ import annotations

from datetime import datetime

from mcp.server.fastmcp import FastMCP  # type: ignore[attr-defined]

from mcp_server.services.billing_service import MCPBillingService
from mcp_server.tools.billing import create_credit_tool, request_approval_tool
from mcp_server.tools.contract import get_contract_tool
from mcp_server.tools.customer import get_customer_tool
from mcp_server.tools.invoice import get_invoice_tool

mcp = FastMCP("billing-mcp")
service = MCPBillingService()


@mcp.tool(description="Returns customer information by id.")
async def get_customer(customer_id: str) -> dict[str, str]:
    return await get_customer_tool(service, customer_id)


@mcp.tool(description="Returns applicable contract summary for a customer.")
async def get_contract(
    customer_id: str,
    issued_at: datetime | None = None,
) -> dict[str, str | None]:
    return await get_contract_tool(service, customer_id, issued_at)


@mcp.tool(description="Returns latest finalized invoice summary for a customer.")
async def get_invoice(customer_id: str) -> dict[str, str]:
    return await get_invoice_tool(service, customer_id)


@mcp.tool(description="Creates a billing credit for a validated discrepancy.")
async def create_credit(
    customer_id: str, invoice_id: str, amount: str, reason: str
) -> dict[str, str]:
    return await create_credit_tool(service, customer_id, invoice_id, amount, reason)


@mcp.tool(
    description="Creates an approval request for a discrepancy requiring human authorization."
)
async def request_approval(customer_id: str, invoice_id: str, amount: str) -> dict[str, str]:
    return await request_approval_tool(service, customer_id, invoice_id, amount)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

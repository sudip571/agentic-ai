from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from mcp_server.services.billing_service import MCPBillingService
from src.shared.configuration import get_settings

app = FastAPI(title="Billing MCP HTTP", version="0.1.0")
service = MCPBillingService()
settings = get_settings()


class CustomerRequest(BaseModel):
    customer_id: str


class ContractRequest(BaseModel):
    customer_id: str
    issued_at: datetime | None = None


class InvoiceRequest(BaseModel):
    customer_id: str


class CreditRequest(BaseModel):
    customer_id: str
    invoice_id: str
    amount: str
    reason: str


class ApprovalToolRequest(BaseModel):
    customer_id: str
    invoice_id: str
    amount: str


async def verify_mcp_token(
    x_mcp_token: Annotated[str, Header(alias="X-MCP-Token")],
) -> None:
    if not secrets.compare_digest(x_mcp_token, settings.mcp_service_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@app.post("/tools/get_customer")
async def get_customer(req: CustomerRequest, _: None = Depends(verify_mcp_token)) -> dict[str, str]:
    return await service.get_customer(req.customer_id)


@app.post("/tools/get_contract")
async def get_contract(
    req: ContractRequest,
    _: None = Depends(verify_mcp_token),
) -> dict[str, str | None]:
    return await service.get_contract(req.customer_id, req.issued_at)


@app.post("/tools/get_invoice")
async def get_invoice(req: InvoiceRequest, _: None = Depends(verify_mcp_token)) -> dict[str, str]:
    return await service.get_invoice(req.customer_id)


@app.post("/tools/create_credit")
async def create_credit(req: CreditRequest, _: None = Depends(verify_mcp_token)) -> dict[str, str]:
    return await service.create_credit(req.customer_id, req.invoice_id, req.amount, req.reason)


@app.post("/tools/request_approval")
async def request_approval(
    req: ApprovalToolRequest,
    _: None = Depends(verify_mcp_token),
) -> dict[str, str]:
    return await service.request_approval(req.customer_id, req.invoice_id, req.amount)

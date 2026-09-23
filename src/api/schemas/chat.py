from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    customer_id: str = Field(..., pattern=r"^CUST-[0-9]{3,}$")
    request_id: str | None = Field(default=None, max_length=64)


class ChatResponse(BaseModel):
    request_id: str
    workflow_id: str
    status: str
    message: str
    requires_human_approval: bool = False
    approval_request_id: str | None = None


class ApprovalActionRequest(BaseModel):
    approver_id: str = Field(..., min_length=3, max_length=128)
    decision: str = Field(..., pattern=r"^(approve|reject)$")

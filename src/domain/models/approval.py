from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.domain.enums.billing_status import ApprovalStatus
from src.domain.models.common import Money


class ApprovalRequest(BaseModel):
    id: str
    request_id: str
    customer_id: str
    invoice_id: str
    amount: Money
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None

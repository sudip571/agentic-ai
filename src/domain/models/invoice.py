from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.domain.enums.billing_status import InvoiceStatus
from src.domain.models.common import Money


class Invoice(BaseModel):
    id: str
    customer_id: str
    billing_period: str
    issued_at: datetime
    total: Money
    status: InvoiceStatus

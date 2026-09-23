from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.domain.models.common import Money


class Credit(BaseModel):
    id: str
    customer_id: str
    invoice_id: str
    amount: Money
    reason: str
    created_at: datetime

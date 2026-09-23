from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.domain.enums.billing_status import ContractStatus
from src.domain.models.common import Money


class Contract(BaseModel):
    id: str
    customer_id: str
    monthly_price: Money
    effective_from: datetime
    effective_to: datetime | None
    status: ContractStatus

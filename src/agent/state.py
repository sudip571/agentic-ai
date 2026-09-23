from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.billing_status import BillingDecision


class BillingAgentState(TypedDict, total=False):
    session: AsyncSession
    request_id: str
    workflow_id: str
    user_message: str
    customer_id: str
    invoice_id: str
    currency: str
    discrepancy: Decimal
    decision: BillingDecision
    decision_reason: str
    status: str
    approval_request_id: str
    credit_id: str
    response_message: str
    error: str

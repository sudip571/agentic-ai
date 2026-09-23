from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.domain.enums.billing_status import BillingDecision


@dataclass(frozen=True)
class BillingRuleInput:
    discrepancy: Decimal
    auto_credit_limit: Decimal
    max_credit_limit: Decimal


@dataclass(frozen=True)
class BillingRuleResult:
    decision: BillingDecision
    reason: str


def evaluate_billing_decision(data: BillingRuleInput) -> BillingRuleResult:
    if data.discrepancy == Decimal("0"):
        return BillingRuleResult(BillingDecision.NO_ACTION, "No discrepancy detected")
    if data.discrepancy < Decimal("0"):
        return BillingRuleResult(
            BillingDecision.MANUAL_INVESTIGATION,
            "Negative discrepancy requires manual investigation",
        )
    if data.discrepancy <= data.auto_credit_limit:
        return BillingRuleResult(BillingDecision.AUTO_CREDIT, "Eligible for automatic credit")
    if data.discrepancy <= data.max_credit_limit:
        return BillingRuleResult(BillingDecision.HUMAN_APPROVAL, "Human approval required")
    return BillingRuleResult(
        BillingDecision.MANUAL_INVESTIGATION,
        "Discrepancy exceeds maximum configured limit",
    )

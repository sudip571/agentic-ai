from decimal import Decimal

from src.domain.enums.billing_status import BillingDecision
from src.domain.rules.billing_rules import BillingRuleInput, evaluate_billing_decision


def test_auto_credit_decision() -> None:
    result = evaluate_billing_decision(
        BillingRuleInput(
            discrepancy=Decimal("20.00"),
            auto_credit_limit=Decimal("25.00"),
            max_credit_limit=Decimal("500.00"),
        )
    )
    assert result.decision == BillingDecision.AUTO_CREDIT


def test_human_approval_decision() -> None:
    result = evaluate_billing_decision(
        BillingRuleInput(
            discrepancy=Decimal("50.00"),
            auto_credit_limit=Decimal("25.00"),
            max_credit_limit=Decimal("500.00"),
        )
    )
    assert result.decision == BillingDecision.HUMAN_APPROVAL


def test_manual_investigation_for_negative() -> None:
    result = evaluate_billing_decision(
        BillingRuleInput(
            discrepancy=Decimal("-10.00"),
            auto_credit_limit=Decimal("25.00"),
            max_credit_limit=Decimal("500.00"),
        )
    )
    assert result.decision == BillingDecision.MANUAL_INVESTIGATION

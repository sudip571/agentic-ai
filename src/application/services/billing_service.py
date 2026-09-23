from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.billing_status import ApprovalStatus, BillingDecision
from src.domain.rules.billing_rules import BillingRuleInput, evaluate_billing_decision
from src.infrastructure.mcp.client import BillingMCPClient
from src.infrastructure.persistence.repositories.billing_repository import BillingRepository
from src.shared.configuration import Settings
from src.shared.errors import ConflictException, NotFoundException, ValidationException
from src.shared.observability import (
    record_approval_completed,
    record_approval_created,
    record_credit_created,
)


@dataclass(frozen=True)
class BillingComputation:
    discrepancy: Decimal
    decision: BillingDecision
    reason: str


@dataclass(frozen=True)
class ApprovalDecisionResult:
    workflow_id: str
    request_id: str
    outcome: str
    customer_id: str
    amount: Decimal


class BillingService:
    def __init__(self, settings: Settings, mcp_client: BillingMCPClient | None = None) -> None:
        self.settings = settings
        self.mcp_client = mcp_client

    async def analyze_customer_billing(
        self,
        session: AsyncSession,
        request_id: str,
        workflow_id: str,
        customer_id: str,
    ) -> tuple[BillingRepository, BillingComputation, str, str]:
        repo = BillingRepository(session)
        if self.mcp_client is None:
            customer = await repo.get_customer(customer_id)
            if not customer:
                raise NotFoundException("Customer not found")

            invoice = await repo.get_latest_finalized_invoice(customer.id)
            if not invoice:
                raise NotFoundException("Finalized invoice not found")

            contract = await repo.get_contract_for_period(customer.id, invoice.issued_at)
            if not contract:
                raise ValidationException("No unique active contract found for invoice period")
        else:
            customer = await self.mcp_client.get_customer(customer_id)
            invoice = await self.mcp_client.get_invoice(customer.id)
            contract = await self.mcp_client.get_contract(customer.id, invoice.issued_at)

        if invoice.total.currency != contract.monthly_price.currency:
            raise ValidationException("Invoice and contract currency mismatch")

        discrepancy = invoice.total.amount - contract.monthly_price.amount
        decision = evaluate_billing_decision(
            BillingRuleInput(
                discrepancy=discrepancy,
                auto_credit_limit=self.settings.auto_credit_limit,
                max_credit_limit=self.settings.max_credit_limit,
            )
        )

        await repo.add_audit_event(
            request_id=request_id,
            workflow_id=workflow_id,
            event_type="DISCREPANCY_CALCULATED",
            actor="system",
            source="billing_service",
            metadata_json=json.dumps({"customer_id": customer.id, "discrepancy": str(discrepancy)}),
        )

        return (
            repo,
            BillingComputation(discrepancy, decision.decision, decision.reason),
            invoice.id,
            invoice.total.currency,
        )

    async def create_credit_if_allowed(
        self,
        repo: BillingRepository,
        request_id: str,
        customer_id: str,
        invoice_id: str,
        discrepancy: Decimal,
        currency: str,
    ) -> str:
        idem_key = f"credit:{request_id}:{customer_id}:{invoice_id}:{discrepancy}"
        inserted = await repo.ensure_idempotency(idem_key, request_id)
        if not inserted:
            raise ConflictException("Duplicate operation detected by idempotency key")

        if self.mcp_client is not None and self.settings.mcp_client_mode == "http":
            credit_id = await self.mcp_client.create_credit(
                customer_id=customer_id,
                invoice_id=invoice_id,
                amount=discrepancy,
                reason="Billing discrepancy auto-correction",
            )
            record_credit_created()
            return credit_id

        credit = await repo.create_credit(
            request_id=request_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount=discrepancy,
            currency=currency,
            reason="Billing discrepancy auto-correction",
        )
        record_credit_created()
        return credit.id

    async def create_approval_request(
        self,
        repo: BillingRepository,
        request_id: str,
        workflow_id: str,
        customer_id: str,
        invoice_id: str,
        discrepancy: Decimal,
        currency: str,
    ) -> str:
        if self.mcp_client is not None and self.settings.mcp_client_mode == "http":
            approval_id = await self.mcp_client.request_approval(
                customer_id=customer_id,
                invoice_id=invoice_id,
                amount=discrepancy,
            )
            record_approval_created()
            return approval_id

        approval = await repo.create_approval(
            request_id=request_id,
            workflow_id=workflow_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount=discrepancy,
            currency=currency,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        record_approval_created()
        return approval.id

    async def process_approval(
        self,
        session: AsyncSession,
        approval_id: str,
        decision: str,
        approver_id: str,
    ) -> ApprovalDecisionResult:
        repo = BillingRepository(session)
        composite = await repo.get_workflow_by_approval(approval_id)
        if not composite:
            raise NotFoundException("Approval request not found")

        approval = composite["approval"]
        workflow = composite["workflow"]

        if approval.status != ApprovalStatus.PENDING.value:
            raise ConflictException("Approval already completed")
        expires_at = approval.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            approval.status = ApprovalStatus.EXPIRED.value
            await repo.upsert_workflow_state(
                workflow.workflow_id,
                workflow.request_id,
                "FAILED",
                json.dumps({"approval_id": approval_id, "reason": "expired"}),
            )
            await session.flush()
            raise ValidationException("Approval expired")

        if decision == "approve":
            await repo.set_approval_decision(approval, ApprovalStatus.APPROVED, approver_id)
            credit_id = await self.create_credit_if_allowed(
                repo=repo,
                request_id=workflow.request_id,
                customer_id=approval.customer_id,
                invoice_id=approval.invoice_id,
                discrepancy=approval.amount,
                currency=approval.currency,
            )
            await repo.add_audit_event(
                request_id=workflow.request_id,
                workflow_id=workflow.workflow_id,
                event_type="APPROVAL_GRANTED",
                actor=approver_id,
                source="approval_endpoint",
                metadata_json=json.dumps({"approval_id": approval_id}),
            )
            await repo.add_audit_event(
                request_id=workflow.request_id,
                workflow_id=workflow.workflow_id,
                event_type="CREDIT_CREATED",
                actor="system",
                source="billing_service",
                metadata_json=json.dumps({"credit_id": credit_id, "approval_id": approval_id}),
            )
            await repo.upsert_workflow_state(
                workflow.workflow_id,
                workflow.request_id,
                "COMPLETED",
                json.dumps(
                    {
                        "approval_id": approval_id,
                        "credit_id": credit_id,
                        "outcome": "approved",
                    }
                ),
            )
            record_approval_completed("approved")
            return ApprovalDecisionResult(
                workflow_id=workflow.workflow_id,
                request_id=workflow.request_id,
                outcome="approved",
                customer_id=approval.customer_id,
                amount=approval.amount,
            )

        await repo.set_approval_decision(approval, ApprovalStatus.REJECTED, approver_id)
        await repo.add_audit_event(
            request_id=workflow.request_id,
            workflow_id=workflow.workflow_id,
            event_type="APPROVAL_REJECTED",
            actor=approver_id,
            source="approval_endpoint",
            metadata_json=json.dumps({"approval_id": approval_id}),
        )
        await repo.upsert_workflow_state(
            workflow.workflow_id,
            workflow.request_id,
            "COMPLETED",
            json.dumps({"approval_id": approval_id, "outcome": "rejected"}),
        )
        record_approval_completed("rejected")
        return ApprovalDecisionResult(
            workflow_id=workflow.workflow_id,
            request_id=workflow.request_id,
            outcome="rejected",
            customer_id=approval.customer_id,
            amount=approval.amount,
        )

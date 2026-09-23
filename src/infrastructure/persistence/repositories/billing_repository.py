from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.billing_status import (
    ApprovalStatus,
    ContractStatus,
    CustomerStatus,
    InvoiceStatus,
)
from src.domain.models.approval import ApprovalRequest
from src.domain.models.common import Money
from src.domain.models.contract import Contract
from src.domain.models.credit import Credit
from src.domain.models.customer import Customer
from src.domain.models.invoice import Invoice
from src.infrastructure.persistence.models import (
    ApprovalRequestTable,
    AuditEventTable,
    ContractTable,
    CreditTable,
    CustomerTable,
    IdempotencyKeyTable,
    InvoiceTable,
    WorkflowRunTable,
)
from src.shared.errors import ConflictException


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_customer(self, customer_id: str) -> Customer | None:
        row = await self.session.get(CustomerTable, customer_id)
        if not row:
            return None
        return Customer(id=row.id, email=row.email, status=CustomerStatus(row.status.upper()))

    async def get_contract_for_period(self, customer_id: str, at: datetime) -> Contract | None:
        query = select(ContractTable).where(
            and_(
                ContractTable.customer_id == customer_id,
                func.upper(ContractTable.status) == ContractStatus.ACTIVE.value,
                ContractTable.effective_from <= at,
            )
        )
        rows = (await self.session.execute(query)).scalars().all()
        valid = [row for row in rows if row.effective_to is None or row.effective_to >= at]
        if len(valid) != 1:
            return None
        row = valid[0]
        return Contract(
            id=row.id,
            customer_id=row.customer_id,
            monthly_price=Money(
                amount=row.monthly_price_amount, currency=row.monthly_price_currency
            ),
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            status=ContractStatus(row.status.upper()),
        )

    async def get_latest_finalized_invoice(self, customer_id: str) -> Invoice | None:
        query = (
            select(InvoiceTable)
            .where(
                and_(
                    InvoiceTable.customer_id == customer_id,
                    func.upper(InvoiceTable.status) == InvoiceStatus.FINALIZED.value,
                )
            )
            .order_by(InvoiceTable.issued_at.desc())
            .limit(1)
        )
        row = (await self.session.execute(query)).scalars().first()
        if not row:
            return None
        return Invoice(
            id=row.id,
            customer_id=row.customer_id,
            billing_period=row.billing_period,
            issued_at=row.issued_at,
            total=Money(amount=row.total_amount, currency=row.total_currency),
            status=InvoiceStatus(row.status.upper()),
        )

    async def ensure_idempotency(self, key: str, request_id: str) -> bool:
        existing = await self.session.get(IdempotencyKeyTable, key)
        if existing:
            return False
        self.session.add(
            IdempotencyKeyTable(key=key, request_id=request_id, created_at=datetime.now(UTC))
        )
        await self.session.flush()
        return True

    async def create_credit(
        self,
        request_id: str,
        customer_id: str,
        invoice_id: str,
        amount: Decimal,
        currency: str,
        reason: str,
    ) -> Credit:
        row = CreditTable(
            request_id=request_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            reason=reason,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self.session.flush()
        return Credit(
            id=row.id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount=Money(amount=amount, currency=currency),
            reason=reason,
            created_at=row.created_at,
        )

    async def create_approval(
        self,
        request_id: str,
        workflow_id: str,
        customer_id: str,
        invoice_id: str,
        amount: Decimal,
        currency: str,
        expires_at: datetime,
    ) -> ApprovalRequest:
        row = ApprovalRequestTable(
            request_id=request_id,
            workflow_id=workflow_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            status=ApprovalStatus.PENDING.value,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return ApprovalRequest(
            id=row.id,
            request_id=row.request_id,
            customer_id=row.customer_id,
            invoice_id=row.invoice_id,
            amount=Money(amount=row.amount, currency=row.currency),
            status=ApprovalStatus(row.status),
            created_at=row.created_at,
            expires_at=row.expires_at,
        )

    async def get_approval(self, approval_id: str) -> ApprovalRequestTable | None:
        return await self.session.get(ApprovalRequestTable, approval_id)

    async def set_approval_decision(
        self,
        approval: ApprovalRequestTable,
        decision: ApprovalStatus,
        approver: str,
    ) -> None:
        approval.status = decision.value
        approval.approved_by = approver
        approval.approved_at = datetime.now(UTC)
        await self.session.flush()

    async def add_audit_event(
        self,
        request_id: str,
        workflow_id: str,
        event_type: str,
        actor: str,
        source: str,
        metadata_json: str,
    ) -> None:
        self.session.add(
            AuditEventTable(
                request_id=request_id,
                workflow_id=workflow_id,
                event_type=event_type,
                actor=actor,
                source=source,
                metadata_json=metadata_json,
                created_at=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def upsert_workflow_state(
        self, workflow_id: str, request_id: str, status: str, state_json: str
    ) -> None:
        row = await self.session.get(WorkflowRunTable, workflow_id)
        now = datetime.now(UTC)
        if row:
            row.status = status
            row.state_json = state_json
            row.updated_at = now
        else:
            self.session.add(
                WorkflowRunTable(
                    workflow_id=workflow_id,
                    request_id=request_id,
                    status=status,
                    state_json=state_json,
                    created_at=now,
                    updated_at=now,
                )
            )
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if "workflow_runs.request_id" in str(exc):
                raise ConflictException("Duplicate request detected") from exc
            raise

    async def get_workflow_by_approval(self, approval_id: str) -> dict[str, Any] | None:
        approval = await self.session.get(ApprovalRequestTable, approval_id)
        if not approval:
            return None
        workflow = await self.session.get(WorkflowRunTable, approval.workflow_id)
        if not workflow:
            return None
        return {"approval": approval, "workflow": workflow}

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.repositories.billing_repository import BillingRepository
from src.shared.configuration import Settings, get_settings
from src.shared.errors import NotFoundException, ValidationException


class MCPBillingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._database = Database(self._settings)

    async def get_customer(self, customer_id: str) -> dict[str, str]:
        async for session in self._database.get_session():
            repo = BillingRepository(session)
            customer = await repo.get_customer(customer_id)
            if not customer:
                raise NotFoundException("Customer not found")
            return {
                "customer_id": customer.id,
                "email": customer.email,
                "status": customer.status.value,
            }
        raise NotFoundException("Customer not found")

    async def get_contract(
        self,
        customer_id: str,
        issued_at: datetime | None = None,
    ) -> dict[str, str | None]:
        async for session in self._database.get_session():
            repo = BillingRepository(session)
            lookup_at = issued_at
            if lookup_at is None:
                invoice = await repo.get_latest_finalized_invoice(customer_id)
                if not invoice:
                    raise NotFoundException("Finalized invoice not found")
                lookup_at = invoice.issued_at

            contract = await repo.get_contract_for_period(customer_id, lookup_at)
            if not contract:
                raise ValidationException("No unique active contract found for invoice period")

            return {
                "contract_id": contract.id,
                "customer_id": contract.customer_id,
                "monthly_price": str(contract.monthly_price.amount),
                "currency": contract.monthly_price.currency,
                "effective_from": contract.effective_from.isoformat(),
                "effective_to": (
                    contract.effective_to.isoformat() if contract.effective_to is not None else None
                ),
                "status": contract.status.value,
            }
        raise NotFoundException("Contract not found")

    async def get_invoice(self, customer_id: str) -> dict[str, str]:
        async for session in self._database.get_session():
            repo = BillingRepository(session)
            invoice = await repo.get_latest_finalized_invoice(customer_id)
            if not invoice:
                raise NotFoundException("Finalized invoice not found")
            return {
                "invoice_id": invoice.id,
                "customer_id": invoice.customer_id,
                "billing_period": invoice.billing_period,
                "issued_at": invoice.issued_at.isoformat(),
                "total": str(invoice.total.amount),
                "currency": invoice.total.currency,
                "status": invoice.status.value,
            }
        raise NotFoundException("Invoice not found")

    async def create_credit(
        self, customer_id: str, invoice_id: str, amount: str, reason: str
    ) -> dict[str, str]:
        async for session in self._database.get_session():
            repo = BillingRepository(session)
            credit = await repo.create_credit(
                request_id=f"mcp-{uuid4()}",
                customer_id=customer_id,
                invoice_id=invoice_id,
                amount=Decimal(amount),
                currency=self._settings.supported_currency,
                reason=reason,
            )
            await session.commit()
            return {
                "credit_id": credit.id,
                "customer_id": customer_id,
                "invoice_id": invoice_id,
                "amount": amount,
                "reason": reason,
                "status": "created",
            }
        raise ValidationException("Unable to create credit")

    async def request_approval(
        self, customer_id: str, invoice_id: str, amount: str
    ) -> dict[str, str]:
        async for session in self._database.get_session():
            repo = BillingRepository(session)
            approval = await repo.create_approval(
                request_id=f"mcp-{uuid4()}",
                workflow_id=f"mcp-{uuid4()}",
                customer_id=customer_id,
                invoice_id=invoice_id,
                amount=Decimal(amount),
                currency=self._settings.supported_currency,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
            await session.commit()
            return {
                "approval_id": approval.id,
                "customer_id": customer_id,
                "invoice_id": invoice_id,
                "amount": amount,
                "status": "pending",
            }
        raise ValidationException("Unable to create approval")

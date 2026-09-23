from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.models import ContractTable, CustomerTable, InvoiceTable
from src.shared.configuration import get_settings


async def seed() -> None:
    settings = get_settings()
    db = Database(settings)
    await db.create_schema()

    async for session in db.get_session():
        exists = await session.scalar(
            select(CustomerTable.id).where(CustomerTable.id == "CUST-001")
        )
        if exists:
            return

        now = datetime.now(UTC)

        session.add_all(
            [
                CustomerTable(id="CUST-001", email="cust001@example.com", status="ACTIVE"),
                CustomerTable(id="CUST-002", email="cust002@example.com", status="ACTIVE"),
            ]
        )
        await session.flush()

        session.add_all(
            [
                ContractTable(
                    id="CONT-001",
                    customer_id="CUST-001",
                    monthly_price_amount=Decimal("100.00"),
                    monthly_price_currency="USD",
                    effective_from=now,
                    effective_to=None,
                    status="ACTIVE",
                ),
                ContractTable(
                    id="CONT-002",
                    customer_id="CUST-002",
                    monthly_price_amount=Decimal("100.00"),
                    monthly_price_currency="USD",
                    effective_from=now,
                    effective_to=None,
                    status="ACTIVE",
                ),
            ]
        )
        await session.flush()

        session.add_all(
            [
                InvoiceTable(
                    id="INV-001",
                    customer_id="CUST-001",
                    billing_period="2026-09",
                    issued_at=now,
                    total_amount=Decimal("150.00"),
                    total_currency="USD",
                    status="FINALIZED",
                ),
                InvoiceTable(
                    id="INV-002",
                    customer_id="CUST-002",
                    billing_period="2026-09",
                    issued_at=now,
                    total_amount=Decimal("100.00"),
                    total_currency="USD",
                    status="FINALIZED",
                ),
            ]
        )

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())

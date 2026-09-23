from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class Money(BaseModel):
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    currency: str = Field(..., min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

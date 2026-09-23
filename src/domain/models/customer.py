from pydantic import BaseModel, Field

from src.domain.enums.billing_status import CustomerStatus


class Customer(BaseModel):
    id: str = Field(..., pattern=r"^CUST-[0-9]{3,}$")
    email: str
    status: CustomerStatus

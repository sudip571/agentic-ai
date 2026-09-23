from enum import StrEnum


class CustomerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class ContractStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class InvoiceStatus(StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class BillingDecision(StrEnum):
    NO_ACTION = "NO_ACTION"
    AUTO_CREDIT = "AUTO_CREDIT"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    MANUAL_INVESTIGATION = "MANUAL_INVESTIGATION"

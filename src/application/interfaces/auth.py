from enum import StrEnum


class Permission(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    APPROVE = "APPROVE"
    ADMIN = "ADMIN"

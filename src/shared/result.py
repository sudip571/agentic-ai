from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Result[T]:
    success: bool
    value: T | None = None
    error: str | None = None

    @staticmethod
    def ok(value: T) -> Result[T]:
        return Result(success=True, value=value)

    @staticmethod
    def fail(error: str) -> Result[T]:
        return Result(success=False, error=error)

# ADR-002 Money Uses Decimal

## Context

Financial values must not use floating-point arithmetic.

## Decision

Use Decimal for all monetary values in domain and persistence contracts.

## Alternatives

- float (rejected due to precision risk).

## Consequences

- Deterministic arithmetic.
- Slightly more explicit conversion handling.

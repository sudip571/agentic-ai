# ADR-007 Money Representation Uses Decimal

## Context

Floating-point arithmetic is unsafe for financial calculations.

## Decision

Represent money using Decimal and explicit currency fields across domain models, persistence, and tool payloads.

## Alternatives

- float/double values.
- integer cents everywhere without currency fields.

## Consequences

- Deterministic and auditable arithmetic behavior.
- Slightly more explicit parsing/conversion logic at boundaries.

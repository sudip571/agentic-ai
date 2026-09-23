# ADR-001 Vertical Slice Architecture

## Context

Billing behavior spans API, workflow, domain rules, and persistence.

## Decision

Use vertical feature-centric modules with clean boundaries.

## Alternatives

- Horizontal layers only (services/repositories/controllers) with high cross-file sprawl.

## Consequences

- Better feature discoverability.
- More explicit dependency direction.

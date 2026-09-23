# ADR-004 MCP Capability Boundary

## Context

The system needs a strict, auditable boundary between AI interpretation and enterprise capabilities (customer lookup, contract lookup, invoice lookup, credit and approval operations).

## Decision

Expose business capabilities through MCP-style tool endpoints and consume them through a typed MCP client adapter.

## Alternatives

- Direct repository calls from workflow for all operations.
- Generic SQL execution tool exposed to the model.

## Consequences

- Better security and least-privilege control for tool access.
- Improved contract testability.
- Added complexity for client/server boundary and resilience handling.

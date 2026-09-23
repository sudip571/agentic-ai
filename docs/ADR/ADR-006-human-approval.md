# ADR-006 Human Approval for Mid/High Discrepancies

## Context

Financial corrections above auto-credit thresholds must not be executed automatically.

## Decision

Introduce persisted approval requests and explicit approval endpoint handling. Workflow returns a waiting-for-approval state for eligible discrepancies.

## Alternatives

- LLM-driven approval recommendation without explicit human gate.
- Fully manual process with no workflow persistence.

## Consequences

- Stronger control over financial side effects.
- Better auditability.
- Requires secure approver authorization and lifecycle handling.

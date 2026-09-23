# ADR-005 LangGraph for Workflow Orchestration

## Context

Billing dispute handling is a multi-step stateful process with branching, side effects, and human-approval pauses.

## Decision

Use LangGraph to model workflow state and ordered node execution with explicit transitions.

## Alternatives

- Single service method with deeply nested branching.
- Ad-hoc task queue orchestration without explicit workflow state.

## Consequences

- Clearer execution flow and state evolution.
- Easier extension for pause/resume behavior.
- Additional framework concepts that must be documented and tested.

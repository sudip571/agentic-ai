# Architecture

## Layered Flow

API -> Agent/Application -> Domain -> Infrastructure.

## Runtime Flow

1. API receives billing complaint.
2. Workflow builds state with ids.
3. LangChain prompt/parsing layer shapes and validates semantic extraction.
4. LiteLLM executes the configured model call.
4. Repository loads invoice and applicable contract.
5. Deterministic discrepancy + decision logic runs.
6. Side-effect path performs idempotent credit or creates approval.
7. Audit and workflow records are persisted.

If approval is required:

1. Workflow stores WAITING_APPROVAL state and returns approval id.
2. Authorized approver calls approval decision endpoint.
3. Application validates status/expiration/idempotency and resumes workflow.
4. Credit is created (or rejected), workflow is finalized, and notification is sent.

## Separation of Responsibilities

- LLM: semantic extraction.
- LangChain: prompt and structured output abstraction.
- Domain rules: financial decision.
- Infrastructure: persistence and external integration.
- Workflow: execution ordering and pause/resume semantics.

## Observability

- `/metrics` exposes Prometheus-compatible counters/histograms.
- Middleware records HTTP duration and outcome metrics.
- Workflow records run duration and outcome.
- LLM adapter records call duration, outcome, and token usage.
- MCP client records tool-call duration, outcomes, and failures.
- Business counters track credits created and approval lifecycle outcomes.
- `X-Trace-Id` is propagated for request-level correlation.

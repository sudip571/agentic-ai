# Billing Agent - Developer Guide

## 1. Project Overview

Billing Agent is a production-oriented reference implementation for AI-assisted billing dispute handling.

Key principle:

- LLM interprets language.
- Application validates data.
- Domain rules decide outcomes.
- Authorized services execute side effects.

## 2. What We Built

Implemented capabilities:

1. FastAPI API with typed request and response models.
2. Structured billing workflow using LangGraph.
3. Deterministic discrepancy and approval rules.
4. SQLAlchemy persistence with strong constraints.
5. MCP boundary with local and HTTP client modes.
6. MCP token auth for HTTP mode.
7. Retry + backoff + circuit breaker for MCP HTTP calls.
8. Idempotency and duplicate request conflict handling.
9. Human-approval persistence, pause/resume, and approval decision processing.
10. LangChain prompt + structured output parser integration for request understanding.
11. API production safeguards: request-size limits, security headers, and rate limiting.
12. Observability stack with Prometheus-compatible metrics and trace-id propagation.
13. Unit, contract, and API integration safety tests.
14. Initial Alembic migration baseline.

## 3. Phase Status Table

| Phase | Description          | Status      |
| ----- | -------------------- | ----------- |
| 0     | Repository/bootstrap | COMPLETED   |
| 1     | Raw LLM + Ollama     | COMPLETED   |
| 2     | Structured output    | COMPLETED   |
| 3     | Tool calling         | COMPLETED   |
| 4     | Database/domain      | COMPLETED   |
| 5     | MCP Server           | COMPLETED   |
| 6     | MCP Client           | COMPLETED   |
| 7     | LiteLLM              | COMPLETED   |
| 8     | LangChain            | COMPLETED   |
| 9     | LangGraph            | COMPLETED   |
| 10    | Human-in-the-loop    | COMPLETED   |
| 11    | Production hardening | COMPLETED   |
| 12    | Deployment           | COMPLETED   |

## 4. Runtime Request Flow

POST /api/chat:

1. FastAPI validates payload and authorization (API key mode or OIDC introspection mode).
2. Workflow state is created with request_id + workflow_id.
3. Understand node parses semantic intent and values.
4. Evaluate node retrieves customer, invoice, and contract via MCP client mode.
5. Domain rules compute discrepancy and decision.
6. Side-effect node:
   - auto-credit path -> create credit
   - approval path -> create approval request and return waiting state
   - no-action/manual path -> finalize with explanation
7. Workflow state + audit events are persisted.
8. Response returns status, message, and approval identifier when needed.

## 5. Data Flow

- API schema -> workflow state.
- Workflow state -> MCP tool payloads and deterministic services.
- Persistence writes:
  - workflow_runs
  - audit_events
  - credits (auto path)
  - approval_requests (approval path)
  - idempotency_keys

## 6. AI Flow

- User message is formatted by LangChain prompt templates.
- LiteLLM executes model inference using configured provider/model.
- LangChain structured output parser validates extracted semantic fields.
- Application validates and uses deterministic logic for financial decisions.
- LLM does not decide authorization, thresholds, or commit behavior.

## 6.1 LangChain Explained

What is it?

- A framework layer for prompt templates and structured parsing primitives.

Why do we need it?

- It standardizes prompt assets and output parsing instead of ad-hoc string handling.

Where is it used?

- src/infrastructure/llm/client.py for prompt composition and Pydantic output parsing.

What happens at runtime?

- LangChain builds the system/human prompt messages.
- LiteLLM executes the model call.
- LangChain parser validates and converts output to typed request data.

What happens if it fails?

- The application safely falls back to regex extraction and still avoids unsafe side effects.

What code did it replace?

- It replaced prompt/message and output parsing logic that was hand-built in the LLM adapter.

## 7. Architecture Summary

API -> Application/Agent -> Domain -> Infrastructure.

- API: request validation, auth checks, error mapping.
- Agent: execution order and workflow transitions.
- Domain: discrepancy/approval rules.
- Infrastructure: persistence, LLM transport, MCP adapters, email adapter.

## 8. LangGraph Explained (Junior-Friendly)

What is it?

- A way to model the workflow as nodes and transitions with explicit state.

Why do we need it?

- Billing dispute handling is multi-step with branching and persistence.

Where is it used?

- Workflow assembly and execution in src/agent/graph.py.

What happens at runtime?

- State enters START, passes understand -> evaluate -> side_effects, then END.

What if it fails?

- Exceptions are surfaced to API handlers and mapped to controlled HTTP responses.

What code did it replace?

- It replaces one giant imperative function with explicit staged nodes and state transitions.

## 9. MCP Explained

What is it?

- A capability boundary exposing narrow business tools (customer/contract/invoice/credit/approval).

Why do we need it?

- Keeps enterprise operations auditable and permission-aware.

Where is it used?

- Server-side tool endpoints in mcp_server.
- Typed client adapter in src/infrastructure/mcp/client.py.

What happens at runtime?

- Local mode calls in-process service adapter.
- HTTP mode calls tool endpoints with service token.

What if it fails?

- Retry/backoff handles transient failures.
- Circuit breaker opens on repeated failures.
- API maps external failures to HTTP 503.

## 10. Business Rules

Implemented deterministic rules:

- discrepancy = invoice - contract
- discrepancy == 0 -> NO_ACTION
- discrepancy < 0 -> MANUAL_INVESTIGATION
- 0 < discrepancy <= AUTO_CREDIT_LIMIT -> AUTO_CREDIT
- AUTO_CREDIT_LIMIT < discrepancy <= MAX_CREDIT_LIMIT -> HUMAN_APPROVAL
- discrepancy > MAX_CREDIT_LIMIT -> MANUAL_INVESTIGATION

## 11. Error Handling

Current exception mapping:

- ValidationException -> 400
- AuthorizationException -> 403
- NotFoundException -> 404
- ConflictException -> 409
- ExternalServiceException -> 503
- Unhandled AppError -> 500

## 12. Security Considerations

Implemented:

- API-key permission tiers for READ/WRITE/APPROVE/ADMIN.
- MCP HTTP token requirement for tool calls.
- Prompt and tool input validation boundaries.
- Idempotency checks for duplicate side-effect prevention.
- Request rate limiting on chat and approval endpoints.
- Request-size protection for chat payloads.
- API security response headers for browser/client hardening.

## 12.1 Observability and Tracing

Implemented:

- `/metrics` endpoint with Prometheus-compatible output.
- Metrics for requests, workflows, LLM, MCP tools, credits, and approvals.
- `X-Trace-Id` propagation for upstream correlation.
- Automatic trace id generation when upstream id is not provided.
- Trace id included in error responses and response headers.

Still needed for full production sign-off:

- Expanded security test matrix and redaction strategy.

## 13. Testing Strategy and Coverage

Current test layers:

- Unit:
  - domain billing rules.
  - LangChain parsing path and fallback behavior.
- Contract:
  - MCP tool metadata and payload contracts.
  - HTTP MCP mode auth, write/read operations, retry/circuit behavior.
- Integration:
  - health endpoints.
  - API safety for MCP circuit-open and duplicate request side effects.
  - approval lifecycle: approve/reject/expire/duplicate/unauthorized.

## 14. Configuration Guide

Important keys:

- APP_NAME, ENVIRONMENT, DATABASE_URL
- MAX_REQUEST_BODY_BYTES, API_RATE_LIMIT_REQUESTS, API_RATE_LIMIT_WINDOW_SECONDS
- AUTH_MODE, AUTH_INTROSPECTION_URL, AUTH_INTROSPECTION_CLIENT_ID
- AUTH_ROLE_CLAIM, AUTH_SCOPE_CLAIM, AUTH_READ_ROLE, AUTH_WRITE_ROLE, AUTH_APPROVE_ROLE, AUTH_ADMIN_ROLE
- LLM_MODEL, LITELLM_BASE_URL, LLM_TIMEOUT_SECONDS
- MCP_CLIENT_MODE, MCP_SERVER_URL, MCP_SERVICE_TOKEN
- MCP_RETRY_ATTEMPTS, MCP_RETRY_BACKOFF_SECONDS
- MCP_CIRCUIT_BREAKER_THRESHOLD, MCP_CIRCUIT_BREAKER_COOLDOWN_SECONDS
- AUTO_CREDIT_LIMIT, MAX_CREDIT_LIMIT
- AUTH_READ_KEY / AUTH_WRITE_KEY / AUTH_APPROVE_KEY / AUTH_ADMIN_KEY

## 15. Operations Quick Start

1. uv sync --extra dev
2. docker compose up -d postgres litellm
3. uv run alembic upgrade head
4. uv run python -m src.infrastructure.persistence.seed
5. uv run uvicorn src.api.main:app --reload
6. uv run uvicorn mcp_server.http_api:app --host 0.0.0.0 --port 9000 (HTTP MCP mode)
7. For GitHub deployment pipeline, follow docs/DEPLOYMENT_GITHUB.md

## 16. Migration Notes

- Alembic baseline migration exists at alembic/versions/20260923_0001_initial_schema.py.
- Use alembic upgrade head in controlled environments.
- Avoid destructive auto-schema operations in production startup.

## 17. Common Errors and Fixes

1. 422 body error on /api/chat:
   Cause: dependency signature mistakes or body shape mismatch.
   Fix: keep dependency providers free of optional body-like parameters.

2. MCP 401 in HTTP mode:
   Cause: token mismatch.
   Fix: align MCP_SERVICE_TOKEN across API and MCP server.

3. MCP circuit breaker open:
   Cause: repeated downstream transport/status failures.
   Fix: resolve MCP dependency health; wait for cooldown or restart service.

## 18. Edge Cases Covered

- Duplicate request_id triggers conflict handling.
- External dependency failure yields safe 503.
- Retry path for transient MCP HTTP failures.
- Circuit open prevents repeated downstream pressure.
- Approval path returns waiting state rather than auto-credit.
- Approval resume handles duplicate and expired decisions safely.

## 19. What Changed From Earlier Iterations

- Added typed MCP client abstraction with local and HTTP modes.
- Added MCP token auth and tool endpoints for write/read operations.
- Added resilience controls (retry/backoff/circuit breaker).
- Added API safety integration tests and conflict mapping.
- Added Alembic migration baseline and additional ADRs.

## 20. What This Does NOT Solve Yet

1. External telemetry exporters (e.g., OTLP/Prometheus scrape infra setup) are not part of this repo.
2. Full infrastructure-as-code provisioning for cloud resources is not part of this repo.
3. Formalized incident response simulations are not part of this repo.

## 21. Phase History

### Phase 0 - Completed

Date: 2026-09-22

Implemented:

- Bootstrap, lint/type/test setup, health API foundation.

### Phase 1 - Completed

Date: 2026-09-22

Implemented:

- Raw LLM parsing client with timeout and fallback behavior.

### Phase 2 - Completed

Date: 2026-09-22

Implemented:

- Structured parsing models and validation boundaries.

### Phase 3 to 7 - Completed

Date: 2026-09-23

Implemented:

- Tool-calling boundaries, DB/domain model, MCP server/client boundary, LiteLLM integration.

### Phase 9 - Completed

Date: 2026-09-23

Implemented:

- LangGraph stateful workflow orchestration with decision-based branching.

### Phase 8 - Completed

Date: 2026-09-23

Implemented:

- LangChain prompt and structured-output parsing primitives integrated into LLM request parsing.

### Phase 10 - Completed

Date: 2026-09-23

Implemented:

- Durable approval lifecycle with approval decision endpoint.
- Resume path creates or rejects credits deterministically.
- Coverage for approve/reject/expire/duplicate/unauthorized approval flows.

### Phase 11 - Completed

Date: 2026-09-23

Implemented:

- API auth/authorization gates and side-effect permissions.
- MCP resilience policies (retry, timeout, circuit breaker).
- Idempotency and duplicate-request conflict handling.
- Request-size limits, rate limiting, and API security headers.
- Observability metrics and trace correlation propagation.

### Phase 12 - Completed

Date: 2026-09-23

Implemented:

- GitHub Actions CI workflow for lint/type/test and container build checks.
- GitHub Actions CD workflow for image publish, migration, and rollout.
- Production deployment model using protected GitHub environment and self-hosted runner.
- OIDC federation to Azure and secret retrieval from Azure Key Vault during deployment.
- Production Docker Compose deployment artifact and rollback guidance.

# Billing Agent

Production-oriented AI Customer Billing Auditor built with Python, FastAPI, LangChain, LangGraph, LiteLLM, and MCP.

## Project Overview

The service accepts billing complaints in natural language, identifies customer billing facts, calculates discrepancies with deterministic domain rules, and either:

- issues an automatic credit,
- creates a human approval request,
- or returns a manual investigation outcome.

The LLM is used only for semantic interpretation. Business rules, authorization, idempotency, and side-effect control are deterministic.
Approval-required workflows are persisted, paused, and resumed through the approval decision API.

## Architecture

User -> FastAPI -> LangGraph workflow -> deterministic services + persistence.

LLM path: FastAPI -> LangGraph -> LangChain prompt/parsing -> LiteLLM -> Ollama model.

Tool path: Agent -> MCP tools (separate server package) -> business services.

## Technology Stack

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- LangGraph
- LangChain
- LiteLLM
- MCP Python SDK
- PostgreSQL (production), SQLite (local dev)
- pytest, ruff, mypy

## Prerequisites

- Python 3.12+
- uv
- Docker (for local Postgres and LiteLLM)
- Ollama (optional for local LLM)

## Installation

```bash
uv sync --extra dev
```

## Configuration

```bash
copy .env.example .env
```

Set values for database, LiteLLM, model, and API keys.
You can tune API hardening controls with MAX_REQUEST_BODY_BYTES, API_RATE_LIMIT_REQUESTS, and API_RATE_LIMIT_WINDOW_SECONDS.

Authentication modes:

- `AUTH_MODE=api_key` for local/dev flows.
- `AUTH_MODE=oidc_introspection` for enterprise identity integration.

For OIDC introspection mode configure:

- `AUTH_INTROSPECTION_URL`
- `AUTH_INTROSPECTION_CLIENT_ID`
- `AUTH_INTROSPECTION_CLIENT_SECRET`
- role/scope mapping keys in `.env.example`

## Running Locally

1. Start dependencies:

```bash
docker compose up -d postgres litellm
```

2. Seed deterministic test data:

```bash
uv run alembic upgrade head
uv run python -m src.infrastructure.persistence.seed
```

3. Run API:

```bash
uv run uvicorn src.api.main:app --reload
```

4. Health:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## Running Tests

```bash
uv run pytest -q
```

## Observability

Metrics endpoint:

```bash
curl http://localhost:8000/metrics
```

The API emits:

- HTTP request totals/failures and latency
- workflow run totals and duration
- LLM call totals/duration/token usage
- MCP tool call totals/failures and duration
- credit and approval counters

Trace correlation:

- Send `X-Trace-Id` to preserve upstream correlation.
- If absent, API generates a trace id and returns it in `X-Trace-Id` response header.

## Database Migrations

Apply migrations:

```bash
uv run alembic upgrade head
```

Create a new migration revision:

```bash
uv run alembic revision -m "describe change"
```

## Running Ollama

Run Ollama separately and pull a model, for example:

```bash
ollama pull qwen2.5:3b
```

## Running LiteLLM

LiteLLM is configured in litellm/config.yaml and exposed on port 4000 via Docker Compose.

## Running MCP Server

```bash
uv run python -m mcp_server.server
```

For HTTP tool mode used by the app MCP client:

```bash
uv run uvicorn mcp_server.http_api:app --host 0.0.0.0 --port 9000
```

Set `MCP_CLIENT_MODE=http` and `MCP_SERVER_URL=http://localhost:9000` to use remote MCP calls.
Set `MCP_SERVICE_TOKEN` to the same value in both API and MCP server environments.
Optional resilience tuning for HTTP mode:

- `MCP_RETRY_ATTEMPTS`
- `MCP_RETRY_BACKOFF_SECONDS`
- `MCP_CIRCUIT_BREAKER_THRESHOLD`
- `MCP_CIRCUIT_BREAKER_COOLDOWN_SECONDS`

Default mode is `MCP_CLIENT_MODE=local` for in-process development.

## Sample Request

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-write-key" \
  -H "X-Actor-Id: user-1" \
  -d '{"message":"My bill is $150 but should be $100","customer_id":"CUST-001"}'
```

If the response requires approval, complete it with:

```bash
curl -X POST http://localhost:8000/api/approvals/<approval_id>/decision \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-approve-key" \
  -H "X-Actor-Id: approver-1" \
  -d '{"approver_id":"approver-1","decision":"approve"}'
```

## Troubleshooting

- Invalid API key -> ensure X-API-Key matches configured keys.
- Customer not found -> run seed script.
- LLM unavailable -> regex fallback parser is used; verify litellm/ollama availability for full behavior.
- DB errors -> confirm DATABASE_URL and postgres health.

## Production Notes

- Enterprise mode uses token introspection (`AUTH_MODE=oidc_introspection`).
- Production secrets are designed for manager-backed retrieval (Azure Key Vault in GitHub CD flow).
- Use GitHub Actions CI/CD workflows under `.github/workflows`.
- Full deployment runbook: `docs/DEPLOYMENT_GITHUB.md`.

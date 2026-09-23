# Billing Agent Up and Running Guide

## 1. Who This Is For

This guide is for a newly joined developer who has never run this project before.
If you follow each step in order, you will be able to:

- Run the API locally
- Run dependencies (Postgres + LiteLLM)
- Optionally run MCP as a separate HTTP service
- Send a working end-to-end request
- Understand what code executes and why
- Add a new feature in a consistent project style

---

## 2. What Is Inside This Project

This repository is one product with multiple runtime parts:

1. API service (FastAPI)
- Entry point: `src/api/main.py`
- Main endpoint for business flow: `POST /api/chat`
- Approval endpoint: `POST /api/approvals/{approval_id}/decision`

2. Agent workflow (LangGraph)
- Workflow orchestration: `src/agent/graph.py`
- Understanding node: `src/agent/nodes/understand_request.py`
- Purpose: controls sequence (understand -> evaluate -> side-effects)

3. Application/domain logic (deterministic business rules)
- Service: `src/application/services/billing_service.py`
- Rules: `src/domain/rules/billing_rules.py`
- Purpose: calculates discrepancy and decides outcomes (no LLM authority here)

4. MCP boundary (tool layer)
- HTTP MCP server: `mcp_server/http_api.py`
- MCP tool service: `mcp_server/services/billing_service.py`
- MCP client adapter: `src/infrastructure/mcp/client.py`

5. Persistence and schema
- Database access and repositories under `src/infrastructure/persistence/`
- Migration config: `alembic.ini`, `alembic/`
- Seed script: `src/infrastructure/persistence/seed.py`

6. Deployment and CI/CD
- Local compose: `docker-compose.yml`
- Production compose: `deploy/compose.prod.yml`
- CI: `.github/workflows/ci.yml`
- CD: `.github/workflows/cd.yml`

---

## 3. Prerequisites You Must Install

Install these on your laptop first.

1. Git
- Verify: `git --version`

2. Python 3.12+
- Verify: `python --version`

3. uv package manager
- Verify: `uv --version`

4. Docker Desktop
- Verify: `docker --version`
- Verify compose: `docker compose version`

5. Optional but recommended tools
- curl (for API tests)
- Postman (manual API testing)
- Ollama (only if you want local model experiments outside current default flow)

---

## 4. First-Time Local Setup

Open PowerShell and go to project root:

```powershell
cd "C:\Projects\Test and Experiemnt\BillingAgentAppTest"
```

### Step 1: Create local env file

```powershell
Copy-Item .env.example .env
```

### Step 2: Install Python dependencies

```powershell
$env:UV_NATIVE_TLS='true'
uv sync --extra dev
```

### Step 3: Start runtime dependencies (Postgres + LiteLLM)

```powershell
docker compose up -d postgres litellm
```

### Step 4: Run database migration

```powershell
uv run alembic upgrade head
```

### Step 5: Seed test data

```powershell
uv run python -m src.infrastructure.persistence.seed
```

### Step 6: Start API

```powershell
uv run uvicorn src.api.main:app --reload
```

### Step 7: Health checks

```powershell
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/metrics
```

If these endpoints respond successfully, your local setup is running correctly.

---

## 5. Keys and Config: What To Replace and Where

All runtime config is loaded by `src/shared/configuration.py` from `.env`.

### Local developer mode (safe defaults)

In `.env` keep:

- `AUTH_MODE=api_key`
- API keys:
  - `AUTH_READ_KEY`
  - `AUTH_WRITE_KEY`
  - `AUTH_APPROVE_KEY`
  - `AUTH_ADMIN_KEY`

These keys are used in request headers. Example write key header:

- `X-API-Key: dev-write-key`

### MCP HTTP mode (if using separate MCP process)

Must match between API and MCP server:

- `MCP_CLIENT_MODE=http`
- `MCP_SERVER_URL=http://localhost:9000` (or `http://localhost:9000/mcp`, both are normalized by client code)
- `MCP_SERVICE_TOKEN=<same token on both sides>`

### Enterprise auth mode (not needed for day-1 local)

If enabled, replace these with real identity values:

- `AUTH_MODE=oidc_introspection`
- `AUTH_INTROSPECTION_URL`
- `AUTH_INTROSPECTION_CLIENT_ID`
- `AUTH_INTROSPECTION_CLIENT_SECRET`
- role mapping keys (`AUTH_*_ROLE`, `AUTH_ROLE_CLAIM`, `AUTH_SCOPE_CLAIM`)

---

## 6. How Systems Interact

```mermaid
flowchart LR
    U[Client/User] --> API[FastAPI API\nsrc/api/main.py]
    API --> CHAT[/POST /api/chat\nsrc/api/routes/chat.py/]
    CHAT --> WF[BillingWorkflow\nsrc/agent/graph.py]
    WF --> N1[understand_request]
    WF --> N2[BillingService analyze]
    N2 --> RULES[Domain Rules\nsrc/domain/rules/billing_rules.py]
    N2 --> MCPClient[MCP Client Adapter]
    MCPClient -->|local mode| LocalSvc[MCP Local Service Object]
    MCPClient -->|http mode| MCPHTTP[mcp_server/http_api.py]
    MCPHTTP --> ToolSvc[MCPBillingService]
    N2 --> Repo[(Postgres via SQLAlchemy)]
    WF --> N3[side_effects]
    N3 --> Credit[create credit or approval]
    Credit --> Repo
    API --> RESP[ChatResponse]
```

Simple interpretation:

1. API receives request.
2. Agent workflow runs ordered steps.
3. LLM helps understand message only.
4. Deterministic business rules decide financial action.
5. Result is persisted.
6. Response is returned.

---

## 7. Main Entry Point and Full Request Flow Example

### Main entry point

- App startup and middleware: `src/api/main.py`
- Router binding: `src/api/routes/chat.py`

### Full functional example

#### 1) Send billing complaint

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-write-key" \
  -H "X-Actor-Id: user-1" \
  -d '{"message":"My bill is $150 but should be $100","customer_id":"CUST-001"}'
```

#### 2) What code executes next

1. `src/api/main.py` middleware adds `X-Trace-Id`, applies request limits and security headers.
2. `src/api/routes/chat.py` endpoint validates auth and calls `BillingWorkflow.run(...)`.
3. `src/agent/graph.py` executes:
- `understand` -> uses `src/agent/nodes/understand_request.py` with `LLMClient`
- `evaluate` -> uses `BillingService.analyze_customer_billing(...)`
- `side_effects` -> create credit, create approval, or finalize no-action/manual
4. `src/application/services/billing_service.py` applies deterministic decision from `src/domain/rules/billing_rules.py`.
5. Repository writes workflow + audit + side effects.
6. Response returns status and message.

#### 3) If approval is required

Response includes `approval_request_id`, then execute:

```bash
curl -X POST http://localhost:8000/api/approvals/<approval_id>/decision \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-approve-key" \
  -H "X-Actor-Id: approver-1" \
  -d '{"approver_id":"approver-1","decision":"approve"}'
```

This will run `BillingService.process_approval(...)`, update approval/workflow status, and issue credit if approved.

---

## 8. Running MCP as a Separate App (Optional)

Default is local MCP mode (in-process object calls). Use separate MCP server only if needed.

### Step A: Update `.env`

```env
MCP_CLIENT_MODE=http
MCP_SERVER_URL=http://localhost:9000
MCP_SERVICE_TOKEN=dev-mcp-token
```

### Step B: Start MCP server

```powershell
uv run uvicorn mcp_server.http_api:app --host 0.0.0.0 --port 9000
```

### Step C: Start API normally

```powershell
uv run uvicorn src.api.main:app --reload
```

### Step D: Verify MCP health

```bash
curl http://localhost:9000/health/live
```

---

## 9. A-to-Z Guidance for Adding a New Feature

Use this as your implementation path every time.

1. Understand requirement and classify it
- API contract change?
- Domain rule change?
- Workflow step change?
- External integration change?

2. Read architecture references first
- `Instruction.md`
- `docs/ARCHITECTURE.md`
- ADRs under `docs/ADR/`

3. Start with domain rule if business logic changes
- Add or update rule in `src/domain/rules/`
- Keep rules deterministic and testable

4. Update application service orchestration
- Implement use-case logic in `src/application/services/`
- Keep persistence access through repositories

5. Update workflow if sequence/branching changes
- Edit nodes or transitions in `src/agent/graph.py`
- Keep state explicit

6. Update API schemas and routes
- Request/response models in `src/api/schemas/`
- Endpoints in `src/api/routes/`

7. Add/adjust infrastructure only if needed
- LLM adapter: `src/infrastructure/llm/`
- MCP adapter: `src/infrastructure/mcp/`
- Persistence: `src/infrastructure/persistence/`

8. Write tests before finalizing
- Unit tests for domain and service logic
- Integration tests for API flow
- Contract tests for MCP boundaries

9. Run quality gates locally

```powershell
uv run ruff check .
uv run mypy src mcp_server tests
uv run pytest -q .
```

10. If schema changed, create migration

```powershell
uv run alembic revision -m "describe change"
uv run alembic upgrade head
```

11. Update docs
- Add behavior changes to developer/deployment docs when relevant

12. Open PR with clear checklist
- What changed
- Why changed
- How tested
- Backward compatibility impact

---

## 10. Rules and Boundaries You Must Follow

These are mandatory for consistency.

1. LLM boundaries
- LLM can interpret language only.
- LLM must not decide authorization, money movement, approval thresholds, or final action.

2. Deterministic financial logic
- Keep all billing decisions in domain/application code (`src/domain`, `src/application`).
- Use `Decimal` for money.

3. Layer boundaries
- API layer: validation, auth, HTTP mapping.
- Agent/workflow: orchestration and state transitions.
- Domain: pure business rules.
- Infrastructure: DB, LLM transport, MCP, email.

4. Side-effect safety
- Use idempotency keys for write operations.
- Never create duplicate credits for same request semantics.

5. Security and auth
- Respect permission hierarchy (READ/WRITE/APPROVE/ADMIN).
- Never hardcode production secrets.

6. Error discipline
- Raise typed app errors and let API map to HTTP status.
- Keep external failures surfaced as controlled errors.

7. Observability discipline
- Preserve trace flow (`X-Trace-Id`).
- Do not remove metrics/logging around workflow and external calls.

8. Testing discipline
- Every behavior change must include or update tests.
- Avoid merging feature code without passing lint, typecheck, and test suite.

---

## 11. Quick Troubleshooting

1. Invalid API key
- Verify `X-API-Key` matches `.env` keys.

2. Customer not found
- Seed data again:
  - `uv run python -m src.infrastructure.persistence.seed`

3. MCP 401 in HTTP mode
- Ensure `MCP_SERVICE_TOKEN` is exactly the same in API and MCP environments.

4. Database connection issues
- Ensure Postgres container is healthy and `DATABASE_URL` matches your environment.

5. LLM not responding
- Ensure LiteLLM container is running and `LITELLM_BASE_URL` is reachable.

---

## 12. Day-1 Success Checklist

- `.env` created from `.env.example`
- Dependencies installed with `uv`
- `postgres` and `litellm` containers are healthy
- Migration + seed completed
- API starts on port 8000
- `/health/ready` returns success
- You can run one `POST /api/chat` request successfully
- You understand where to implement your first feature

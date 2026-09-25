# Flightdeck AI Feature Plan (Practical, Scalable, Junior-Friendly)

## 1. Goal

Add a new Flightdeck assistant feature that can:

1. Answer guidance questions for new users.
   - Example: "I need to use share of voice reporting and how to use it"
   - Output: clear step-by-step UI instructions.

2. Run reporting requests for existing users.
   - Example: "I need a report of share of voice for July"
   - Output: request missing parameters, call reporting API, summarize result, return clickable UI link.

Keep implementation simple, modular, and production-safe.

## 1.1 Current Implementation Status

Implemented in code now:

1. New endpoint: `POST /api/flightdeck/chat`.
2. Guidance flow: step-by-step instructions + deep link.
3. Report flow: share_of_voice generation with summary + deep link.
4. Missing-parameter follow-up flow with `conversation_id` continuation.
5. MCP local/HTTP integration path for Flightdeck tools.
6. Integration and unit tests for guidance/report flow, role authz, timeout handling, invalid date ranges, and deep-link generation.
7. MCP contract tests for Flightdeck tool payload shapes and HTTP client mode behavior.
8. Observability tests for trace-id propagation and Flightdeck endpoint metrics visibility.

Remaining for production rollout:

1. Replace mock report payload logic with real C# Flightdeck API integration.
2. Add persistent conversation state store (database/redis) instead of in-memory store.
3. Expand report types and role-policy matrix.
4. Complete full CI test matrix defined in FlightDeck-Test-Matrix.md.

---

## 2. Product Principles

1. LLM is for language understanding and summarization only.
2. Deterministic services own business rules, permissions, and side effects.
3. Agent flow must be explicit and state-driven (LangGraph).
4. Every external action (report API call, link generation) is traceable/auditable.
5. Ask only the minimum missing questions to complete the job.
6. Fail safe with actionable user messages.

---

## 3. Scope for First Version (MVP)

### In Scope

1. Intent detection:
   - Guidance intent ("how to use")
   - Report execution intent ("generate report")

2. One report type initially:
   - share_of_voice

3. Slot filling for missing report parameters.

4. API execution via Flightdeck backend (C# service) through MCP boundary.

5. Response formatting:
   - Summary bullets
   - Deep link to frontend report page with filters

6. Auth and permission checks.

7. Observability and error handling.

### Out of Scope (for now)

1. Multi-report orchestration in one request.
2. Background long-running jobs.
3. Multi-language localization.
4. Autonomous browser control in user UI.

---

## 4. Minimal Architecture

Use existing project pattern; do not redesign everything.

1. API layer (FastAPI): receives chat request and auth context.
2. Agent layer (LangGraph): orchestrates node-by-node workflow.
3. LLM adapter (LangChain + LiteLLM):
   - parse user intent/parameters
   - summarize report response
4. Application service layer (deterministic):
   - validate parameters
   - enforce permissions
   - call MCP client
   - build deep links
5. MCP client/server boundary:
   - typed tools for C# reporting API
6. Persistence + audit:
   - workflow states
   - prompts/outputs metadata
   - report call records

---

## 5. Data Contracts to Add

## 5.1 Chat Request (existing + extension)

Keep current base fields and add optional context fields:

1. message: string
2. customer_id or tenant_id from auth/session context
3. request_id (idempotency/correlation)
4. user_context (optional):
   - user_id
   - account_id
   - roles
   - locale
   - timezone

## 5.2 Parsed Intent Schema (LLM output)

Add strongly typed schema (Pydantic) used by parser:

1. intent: guidance | generate_report | unknown
2. report_type: share_of_voice | unknown
3. period:
   - month
   - year
   - date_range
4. dimensions:
   - brand
   - channel
   - market
5. format:
   - summary_only | detailed
6. confidence: float

Validation rules must run after parsing.

## 5.3 Report API Parameters

Define deterministic required fields for share_of_voice:

1. account_id
2. period_start
3. period_end
4. timezone
5. market (if mandatory in your C# API)
6. channel (if mandatory)

---

## 6. LangGraph Workflow (Simple but Complete)

Recommended nodes:

1. understand_request
   - LLM parse into typed intent schema.

2. resolve_user_context
   - read auth/session-derived user/account scope.

3. classify_path
   - branch to guidance path or reporting path.

4. collect_missing_parameters (report path)
   - compare extracted params vs required params.
   - ask targeted follow-up questions if missing.

5. authorize_action
   - verify user can access requested report and dimensions.

6. execute_report (report path)
   - call MCP tool to C# report API.

7. summarize_report (report path)
   - LLM summarizes deterministic result payload.

8. generate_deep_link (report path)
   - create clickable frontend URL with filters.

9. guidance_response (guidance path)
   - return step-by-step usage instructions.

10. finalize_response
   - standard output format and metadata.

### Branching Rules

1. intent == guidance -> guidance_response -> finalize
2. intent == generate_report and missing params -> ask question(s) -> wait
3. intent == generate_report and params complete -> authorize -> execute -> summarize -> link -> finalize
4. unknown intent -> safe clarification question

---

## 7. LiteLLM Best Practices

1. Use model aliases in LiteLLM config:
   - flightdeck-local
   - flightdeck-openai
   - flightdeck-balanced

2. Keep cost/token telemetry on for each call.

3. Enforce timeout and retries at LiteLLM/router level.

4. Separate prompts by purpose:
   - intent parser prompt
   - report summarizer prompt
   - guidance formatter prompt

5. Apply strict output schema for parser calls.

6. Implement fallback parser for dates/months if LLM parse fails.

7. Never let LLM directly choose API endpoint or permissions.

---

## 8. LangChain Best Practices

1. Use ChatPromptTemplate for system + user messages.
2. Use PydanticOutputParser or structured output parser.
3. Keep parser prompt short and schema-driven.
4. Add deterministic post-parse normalization:
   - map "July" to date range with timezone
   - normalize channel names
5. Keep summarization separate from parsing.

---

## 9. MCP Server Design for Flightdeck

Add minimal typed tools under MCP boundary:

1. get_report_capabilities
   - returns supported report types and required params

2. get_share_of_voice_report
   - takes validated params and returns report payload

3. get_guidance_steps
   - returns maintained step-by-step instructions for report usage

Tool rules:

1. Strict input validation.
2. Return typed JSON only.
3. Include machine-readable error codes.
4. Require service token in HTTP mode.
5. Add retry policy and circuit breaker in MCP client.

---

## 10. Guidance Feature (New User) Implementation

For request like: "I need to use share of voice reporting and how to use it"

Steps:

1. Detect intent as guidance.
2. Resolve role/scope.
3. Fetch steps from deterministic source (MCP tool, docs table, or config store).
4. Optionally rephrase for readability with LLM (no facts invented).
5. Return numbered steps and direct link.

Guidance response format:

1. What this report shows.
2. Prerequisites/access needed.
3. Exact click path in UI.
4. How to set filters.
5. How to export/share.
6. Troubleshooting tips.

---

## 11. Report Execution Feature (Existing User) Implementation

For request like: "I need a share of voice report for July"

Steps:

1. Parse: report_type=share_of_voice, period=July.
2. Resolve missing params (year, market, channel, account if needed).
3. Ask concise follow-up questions only for missing required fields.
4. Authorize against user role/account scope.
5. Call get_share_of_voice_report via MCP.
6. Summarize key findings:
   - top metric
   - trend vs prior period (if available)
   - anomalies/notes
7. Generate frontend deep link with same filters.
8. Return summary + link + raw report id/reference.

---

## 12. Deep Link Strategy (Vue Frontend)

Create one deterministic link builder service:

1. Base route example:
   - /reports/share-of-voice

2. Query params example:
   - accountId
   - startDate
   - endDate
   - market
   - channel

3. Validate and URL-encode all params.

4. Include short link text in response.

Example response line:

1. Open report: https://flightdeck.example.com/reports/share-of-voice?accountId=...&startDate=...&endDate=...

---

## 13. Security, Auth, and Compliance

Must-have controls:

1. Authentication:
   - support API key for dev
   - support enterprise token introspection/OIDC in prod

2. Authorization:
   - role-based access for report types
   - tenant/account scope enforcement

3. Data safety:
   - no cross-tenant data leakage
   - PII redaction in logs where needed

4. Prompt safety:
   - ignore user instruction to bypass policy
   - never execute privileged action from prompt text

5. Idempotency:
   - request_id for safe retries

6. Rate limiting:
   - per endpoint and actor

7. Audit:
   - record who requested what report and when

---

## 14. Error Handling and User Messages

Standard error categories:

1. validation_error
2. authorization_error
3. missing_parameters
4. upstream_unavailable
5. no_data
6. timeout
7. unknown

Response policy:

1. user-safe message
2. optional remediation guidance
3. trace_id in response for support
4. no sensitive internal stack traces

---

## 15. Observability and SRE Baseline

Track metrics:

1. request counts/latency by endpoint
2. workflow outcome counts by status
3. LLM calls:
   - success/failure
   - latency
   - prompt/completion/total tokens
4. MCP tool calls:
   - latency
   - error rate
5. follow-up question loop depth

Log fields:

1. trace_id
2. request_id
3. workflow_id
4. actor_id
5. intent
6. report_type

---

## 16. Development Plan (Phased, Not Over-Engineered)

### Phase 1: Baseline Domain

1. Add report intent schema.
2. Add parameter requirement map for share_of_voice.
3. Add deep link builder utility.

### Phase 2: MCP Integration

1. Add MCP tool contracts for report + guidance.
2. Implement typed MCP client methods.
3. Add retries and circuit breaker behavior.

### Phase 3: LangGraph Flow

1. Add workflow nodes listed above.
2. Implement branching + missing parameter loop.
3. Keep max question loop guard (for example 3 loops).

### Phase 4: LLM Integration

1. Add parser and summarizer prompts.
2. Enforce structured output.
3. Add deterministic fallback for date parsing.

### Phase 5: Security + Hardening

1. Add role/scope checks.
2. Add stricter validation and error mapping.
3. Add rate limit and idempotency checks.

### Phase 6: Testing

1. Unit tests for rules/normalizers/link builder.
2. Contract tests for MCP tools.
3. Integration tests for end-to-end scenarios.
4. Negative tests for auth and missing params.

---

## 17. Test Matrix (Minimum)

### Guidance Intent

1. valid guidance request -> returns numbered steps and link
2. unauthorized user -> proper 403
3. unknown report type -> clarification response

### Report Intent

1. complete parameters -> report + summary + deep link
2. missing parameters -> asks targeted question
3. invalid period -> validation message
4. no data for period -> graceful no-data response
5. API timeout -> retry then safe failure
6. cross-tenant access attempt -> blocked

### Safety

1. prompt injection text -> ignored as policy bypass attempt
2. repeated same request_id -> idempotent behavior

---

## 18. Suggested Folder-Level Additions

Keep naming consistent with existing codebase.

1. src/agent/nodes/
   - classify_intent.py
   - collect_missing_params.py
   - execute_report.py
   - summarize_report.py
   - guidance_response.py

2. src/application/services/
   - report_service.py

3. src/domain/rules/
   - report_rules.py

4. src/infrastructure/mcp/
   - flightdeck_client.py

5. mcp_server/tools/
   - reporting.py
   - guidance.py

6. tests/
   - unit/reporting/
   - contract/mcp/reporting/
   - integration/api/flightdeck/

---

## 19. Junior Developer Checklist

Before opening PR:

1. Feature works for both scenarios (guidance + report).
2. All new inputs are validated.
3. No business decision hidden in prompt logic.
4. Auth checks are covered by tests.
5. Trace id and request id are visible in logs.
6. Error messages are safe and actionable.
7. Docs updated with API examples and screenshots if needed.

---

## 20. Definition of Done

Feature is done when:

1. New user guidance flow works with clear steps and link.
2. Existing user report flow handles missing parameters and returns summary + deep link.
3. Role and tenant boundaries are enforced.
4. LLM, MCP, and workflow metrics are observable.
5. Test matrix passes in CI.
6. Ops docs include startup, config, and troubleshooting for this feature.

---

## 21. Keep It Extendable (for Later Features)

When adding more tools/reports later:

1. Add new report type to parameter map.
2. Add MCP tool contract and implementation.
3. Reuse same LangGraph branch with minimal new nodes.
4. Add tests for new report edge cases.

Avoid building generic framework too early; evolve only from real feature needs.

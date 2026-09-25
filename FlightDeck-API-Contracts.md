# Flightdeck API Contracts

## 1. Purpose

This document defines concrete contracts for the Flightdeck feature introduced in FlightDeck.md.

Goals:

1. Keep contracts simple and explicit.
2. Make implementation easy for junior developers.
3. Ensure deterministic validation before external API calls.
4. Keep room for adding more report types later.

---

## 2. Public Chat API

Endpoint:

- POST /api/chat

Headers:

- X-API-Key: required in api_key mode
- X-Actor-Id: optional but recommended
- X-Trace-Id: optional, generated if not provided

### 2.1 Request Schema

```json
{
  "message": "I need share of voice report for July",
  "customer_id": "CUST-001",
  "request_id": "req-flightdeck-001",
  "context": {
    "tenant_id": "tenant-123",
    "account_id": "acct-456",
    "timezone": "UTC",
    "locale": "en-US"
  }
}
```

Field notes:

1. message: required natural-language input.
2. customer_id: required for now (can later be server-derived from auth).
3. request_id: optional; if omitted, backend generates UUID.
4. context: optional metadata from frontend/session.

### 2.2 Response Schema (Unified)

```json
{
  "request_id": "req-flightdeck-001",
  "workflow_id": "5f0d6fc0-b91f-4548-92a9-d4f260a0f8a8",
  "status": "completed",
  "message": "Share of voice report generated for July 2026.",
  "requires_human_approval": false,
  "approval_request_id": null,
  "assistant": {
    "intent": "generate_report",
    "report_type": "share_of_voice",
    "summary": [
      "Brand A share: 34.2%",
      "Month-over-month change: +2.1%",
      "Top channel: social"
    ],
    "follow_up_questions": [],
    "deep_link": "https://flightdeck.example.com/reports/share-of-voice?accountId=acct-456&startDate=2026-07-01&endDate=2026-07-31&timezone=UTC"
  }
}
```

assistant object rules:

1. summary is optional for guidance path.
2. follow_up_questions is non-empty only when required parameters are missing.
3. deep_link is present only for successful report execution or guidance deep-link target.

---

## 3. Intent Parse Contract (Internal)

Produced by LLM parser node, then validated deterministically.

```json
{
  "intent": "generate_report",
  "report_type": "share_of_voice",
  "time": {
    "month": "july",
    "year": 2026,
    "start_date": null,
    "end_date": null
  },
  "filters": {
    "market": "US",
    "channel": "social",
    "brand": "Brand A"
  },
  "format": "summary_only",
  "confidence": 0.89
}
```

Validation rules:

1. intent must be one of guidance, generate_report, unknown.
2. report_type must be known by capability map.
3. month names normalized to lowercase.
4. if date range provided, start_date <= end_date.
5. confidence not used for authorization decisions.

---

## 4. Missing Parameter Question Contract (Internal)

When required fields are missing, return deterministic question payload.

```json
{
  "status": "waiting_user_input",
  "assistant": {
    "intent": "generate_report",
    "report_type": "share_of_voice",
    "follow_up_questions": [
      {
        "id": "year",
        "question": "Which year do you want for July?",
        "type": "single_value",
        "examples": ["2026", "2025"]
      },
      {
        "id": "market",
        "question": "Which market should I use?",
        "type": "single_value",
        "examples": ["US", "UK", "IN"]
      }
    ]
  }
}
```

Guideline:

- Ask only required missing fields.
- Keep question count minimal and ordered by importance.

---

## 5. Guidance Response Contract

For requests like "How to use share of voice reporting?"

```json
{
  "request_id": "req-flightdeck-002",
  "workflow_id": "4f4735a9-3fd2-4e8f-8845-c87c7f2a4eef",
  "status": "completed",
  "message": "Here is how to use Share of Voice reporting.",
  "assistant": {
    "intent": "guidance",
    "report_type": "share_of_voice",
    "steps": [
      "Open Reports from the left menu.",
      "Select Share of Voice.",
      "Pick the account and date range.",
      "Choose market and channel filters.",
      "Click Run Report.",
      "Use Export to download CSV/PDF."
    ],
    "deep_link": "https://flightdeck.example.com/reports/share-of-voice"
  }
}
```

---

## 6. MCP Tool Contracts

These are internal service boundary contracts between app and MCP server.

## 6.1 Tool: get_report_capabilities

Request:

```json
{
  "tenant_id": "tenant-123",
  "role": "analyst"
}
```

Response:

```json
{
  "reports": [
    {
      "report_type": "share_of_voice",
      "required_params": ["account_id", "start_date", "end_date", "timezone"],
      "optional_params": ["market", "channel", "brand"],
      "allowed_roles": ["analyst", "manager", "admin"]
    }
  ]
}
```

## 6.2 Tool: get_guidance_steps

Request:

```json
{
  "report_type": "share_of_voice",
  "role": "analyst"
}
```

Response:

```json
{
  "report_type": "share_of_voice",
  "steps": [
    "Open Reports.",
    "Select Share of Voice.",
    "Set filters.",
    "Run and export."
  ],
  "deep_link": "/reports/share-of-voice"
}
```

## 6.3 Tool: get_share_of_voice_report

Request:

```json
{
  "tenant_id": "tenant-123",
  "account_id": "acct-456",
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "timezone": "UTC",
  "market": "US",
  "channel": "social",
  "brand": "Brand A"
}
```

Response:

```json
{
  "report_id": "sov-2026-07-acct-456",
  "report_type": "share_of_voice",
  "period": {
    "start_date": "2026-07-01",
    "end_date": "2026-07-31",
    "timezone": "UTC"
  },
  "metrics": {
    "share_percent": 34.2,
    "mentions": 12450,
    "rank": 2,
    "mom_change_percent": 2.1
  },
  "breakdown": [
    {"dimension": "social", "share_percent": 40.1},
    {"dimension": "news", "share_percent": 28.7}
  ],
  "generated_at": "2026-09-24T10:15:00Z"
}
```

---

## 7. Deep Link Contract

Use one deterministic builder in application service.

Input:

```json
{
  "base_url": "https://flightdeck.example.com",
  "route": "/reports/share-of-voice",
  "query": {
    "accountId": "acct-456",
    "startDate": "2026-07-01",
    "endDate": "2026-07-31",
    "timezone": "UTC",
    "market": "US",
    "channel": "social",
    "brand": "Brand A"
  }
}
```

Output:

```json
{
  "deep_link": "https://flightdeck.example.com/reports/share-of-voice?accountId=acct-456&startDate=2026-07-01&endDate=2026-07-31&timezone=UTC&market=US&channel=social&brand=Brand%20A"
}
```

Rules:

1. URL-encode all query values.
2. Do not include null fields.
3. Include only allow-listed query keys.

---

## 8. Error Contract

Standard shape:

```json
{
  "detail": "Validation failed: year is required for month-only request",
  "code": "missing_parameters",
  "trace_id": "2b43f6f5ddc744a59780527ca2de6f8c"
}
```

Recommended error codes:

1. validation_error
2. missing_parameters
3. unauthorized
4. forbidden
5. not_found
6. upstream_timeout
7. upstream_unavailable
8. no_data
9. conflict

---

## 9. Auth Contract Guidance

Development mode:

1. API key in X-API-Key
2. Actor id in X-Actor-Id

Production mode:

1. Bearer token with OIDC introspection
2. Tenant and role derived server-side
3. Ignore user-supplied tenant override when token context exists

---

## 10. LiteLLM and LangChain Call Contract (Internal)

LLM parse call input:

```json
{
  "task": "intent_and_parameters_parse",
  "message": "I need share of voice report for July",
  "output_schema": "FlightdeckIntentParse"
}
```

LLM parse call output:

```json
{
  "intent": "generate_report",
  "report_type": "share_of_voice",
  "time": {"month": "july", "year": null, "start_date": null, "end_date": null},
  "filters": {"market": null, "channel": null, "brand": null},
  "format": "summary_only",
  "confidence": 0.9
}
```

Instrumentation captured per call:

1. prompt_tokens
2. completion_tokens
3. total_tokens
4. latency_ms
5. success/failure

---

## 11. Versioning Strategy

For future features/tools, prefer additive changes:

1. Add optional fields first.
2. Keep existing response keys stable.
3. If breaking change is unavoidable, add v2 endpoint and migrate clients gradually.

---

## 12. Quick Implementation Checklist

1. Create Pydantic models for all contracts in this file.
2. Add deterministic validators for period/filter/auth scope.
3. Add MCP client interfaces and tool handlers.
4. Add deep link builder utility and tests.
5. Add response mappers for guidance/report paths.
6. Add OpenAPI examples for each contract.

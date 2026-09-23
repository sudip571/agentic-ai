from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS_TOTAL = Counter(
    "billing_requests_total",
    "Total HTTP requests processed by the API.",
    ["method", "path", "status"],
    registry=REGISTRY,
)

HTTP_REQUESTS_FAILED_TOTAL = Counter(
    "billing_requests_failed_total",
    "HTTP requests that resulted in 4xx or 5xx responses.",
    ["method", "path", "status"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "billing_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
    registry=REGISTRY,
)

WORKFLOW_RUNS_TOTAL = Counter(
    "billing_workflow_runs_total",
    "Number of workflow runs by outcome.",
    ["outcome"],
    registry=REGISTRY,
)

WORKFLOW_DURATION_SECONDS = Histogram(
    "billing_workflow_duration_seconds",
    "Workflow run duration in seconds.",
    ["outcome"],
    registry=REGISTRY,
)

LLM_CALLS_TOTAL = Counter(
    "billing_llm_calls_total",
    "Total LLM calls by outcome.",
    ["outcome"],
    registry=REGISTRY,
)

LLM_DURATION_SECONDS = Histogram(
    "billing_llm_duration_seconds",
    "LLM call duration in seconds.",
    ["outcome"],
    registry=REGISTRY,
)

LLM_TOKENS_TOTAL = Counter(
    "billing_llm_tokens_total",
    "LLM token usage totals.",
    ["token_type"],
    registry=REGISTRY,
)

MCP_TOOL_CALLS_TOTAL = Counter(
    "billing_mcp_tool_calls_total",
    "Total MCP tool calls by tool and outcome.",
    ["tool", "outcome"],
    registry=REGISTRY,
)

MCP_TOOL_DURATION_SECONDS = Histogram(
    "billing_mcp_tool_duration_seconds",
    "MCP tool call duration in seconds.",
    ["tool", "outcome"],
    registry=REGISTRY,
)

MCP_TOOL_FAILURES_TOTAL = Counter(
    "billing_mcp_tool_failures_total",
    "Failed MCP tool calls by tool.",
    ["tool"],
    registry=REGISTRY,
)

CREDITS_CREATED_TOTAL = Counter(
    "billing_credits_created_total",
    "Number of credits created.",
    registry=REGISTRY,
)

APPROVALS_CREATED_TOTAL = Counter(
    "billing_approvals_created_total",
    "Number of approval requests created.",
    registry=REGISTRY,
)

APPROVALS_COMPLETED_TOTAL = Counter(
    "billing_approvals_completed_total",
    "Completed approval decisions by outcome.",
    ["outcome"],
    registry=REGISTRY,
)


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    status = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)
    if status_code >= 400:
        HTTP_REQUESTS_FAILED_TOTAL.labels(method=method, path=path, status=status).inc()


def record_workflow_result(outcome: str, duration_seconds: float) -> None:
    WORKFLOW_RUNS_TOTAL.labels(outcome=outcome).inc()
    WORKFLOW_DURATION_SECONDS.labels(outcome=outcome).observe(duration_seconds)


def record_llm_result(
    outcome: str,
    duration_seconds: float,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
) -> None:
    LLM_CALLS_TOTAL.labels(outcome=outcome).inc()
    LLM_DURATION_SECONDS.labels(outcome=outcome).observe(duration_seconds)
    if prompt_tokens is not None:
        LLM_TOKENS_TOTAL.labels(token_type="prompt").inc(prompt_tokens)
    if completion_tokens is not None:
        LLM_TOKENS_TOTAL.labels(token_type="completion").inc(completion_tokens)
    if total_tokens is not None:
        LLM_TOKENS_TOTAL.labels(token_type="total").inc(total_tokens)


def record_mcp_result(tool: str, outcome: str, duration_seconds: float) -> None:
    MCP_TOOL_CALLS_TOTAL.labels(tool=tool, outcome=outcome).inc()
    MCP_TOOL_DURATION_SECONDS.labels(tool=tool, outcome=outcome).observe(duration_seconds)
    if outcome == "failure":
        MCP_TOOL_FAILURES_TOTAL.labels(tool=tool).inc()


def record_credit_created() -> None:
    CREDITS_CREATED_TOTAL.inc()


def record_approval_created() -> None:
    APPROVALS_CREATED_TOTAL.inc()


def record_approval_completed(outcome: str) -> None:
    APPROVALS_COMPLETED_TOTAL.labels(outcome=outcome).inc()


def render_metrics() -> tuple[bytes, str]:
    payload = generate_latest(REGISTRY)
    return payload, CONTENT_TYPE_LATEST

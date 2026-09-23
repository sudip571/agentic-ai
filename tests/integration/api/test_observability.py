from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app


def test_metrics_endpoint_exposes_observability_counters() -> None:
    client = TestClient(app)

    health = client.get("/health/live")
    assert health.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "billing_requests_total" in metrics.text
    assert "billing_request_duration_seconds" in metrics.text
    assert "billing_workflow_runs_total" in metrics.text


def test_trace_id_is_returned_in_response_headers() -> None:
    client = TestClient(app)
    trace_id = "trace-test-123"

    response = client.get("/health/live", headers={"X-Trace-Id": trace_id})

    assert response.status_code == 200
    assert response.headers.get("X-Trace-Id") == trace_id

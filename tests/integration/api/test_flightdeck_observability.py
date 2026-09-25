from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.dependencies import get_flightdeck_llm_client
from src.api.main import app
from src.infrastructure.llm.flightdeck_client import ParsedFlightdeckIntent
from src.shared.configuration import get_settings


class _GuidanceLLMClient:
    async def parse_intent(self, _: str) -> ParsedFlightdeckIntent:
        return ParsedFlightdeckIntent(intent="guidance", report_type="share_of_voice", confidence=0.9)

    async def summarize_report(self, report_payload: dict[str, object]) -> list[str]:
        return ["summary"]


def test_flightdeck_trace_id_is_returned() -> None:
    settings = get_settings()
    app.dependency_overrides[get_flightdeck_llm_client] = lambda: _GuidanceLLMClient()

    try:
        client = TestClient(app)
        trace_id = "fd-trace-123"
        response = client.post(
            "/api/flightdeck/chat",
            headers={
                "X-API-Key": settings.auth_write_key,
                "X-Actor-Id": "integration-test",
                "X-Trace-Id": trace_id,
            },
            json={
                "message": "How to use share of voice reporting?",
                "customer_id": "CUST-001",
                "request_id": "FD-OBS-001",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("X-Trace-Id") == trace_id
    finally:
        app.dependency_overrides.clear()


def test_flightdeck_metrics_include_chat_path_samples() -> None:
    settings = get_settings()
    app.dependency_overrides[get_flightdeck_llm_client] = lambda: _GuidanceLLMClient()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "How to use share of voice reporting?",
                "customer_id": "CUST-001",
                "request_id": "FD-OBS-002",
            },
        )
        assert response.status_code == 200

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "billing_requests_total" in metrics.text
        assert 'path="/api/flightdeck/chat"' in metrics.text
    finally:
        app.dependency_overrides.clear()

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.dependencies import get_flightdeck_llm_client
from src.api.main import app
from src.infrastructure.llm.flightdeck_client import (
    ParsedFilters,
    ParsedFlightdeckIntent,
    ParsedPeriod,
)
from src.shared.configuration import get_settings


class _FakeFlightdeckLLMClient:
    async def parse_intent(self, message: str) -> ParsedFlightdeckIntent:
        normalized = message.lower()
        if "how to use" in normalized:
            return ParsedFlightdeckIntent(intent="guidance", report_type="share_of_voice")
        if "share of voice" in normalized:
            return ParsedFlightdeckIntent(
                intent="generate_report",
                report_type="share_of_voice",
                period=ParsedPeriod(month="july", year=2026),
                filters=ParsedFilters(),
                confidence=0.9,
            )
        return ParsedFlightdeckIntent(intent="unknown", report_type="share_of_voice")

    async def summarize_report(self, report_payload: dict[str, object]) -> list[str]:
        metrics = report_payload.get("metrics")
        return [f"Metrics available: {bool(metrics)}"]


def test_flightdeck_guidance_request_returns_steps_and_link() -> None:
    settings = get_settings()
    app.dependency_overrides[get_flightdeck_llm_client] = lambda: _FakeFlightdeckLLMClient()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "I need to use share of voice reporting and how to use it",
                "customer_id": "CUST-001",
                "request_id": "FD-GUIDE-001",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["assistant"]["intent"] == "guidance"
        assert len(payload["assistant"]["steps"]) >= 3
        assert isinstance(payload["assistant"]["deep_link"], str)
        assert payload["conversation_id"]
    finally:
        app.dependency_overrides.clear()


def test_flightdeck_report_request_collects_missing_then_completes() -> None:
    settings = get_settings()
    app.dependency_overrides[get_flightdeck_llm_client] = lambda: _FakeFlightdeckLLMClient()

    try:
        client = TestClient(app)
        first = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "I need share of voice report for july 2026",
                "customer_id": "CUST-001",
                "request_id": "FD-REP-001",
                "context": {"role": "analyst"},
            },
        )

        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["status"] == "waiting_user_input"
        assert first_payload["assistant"]["intent"] == "generate_report"
        assert len(first_payload["assistant"]["follow_up_questions"]) >= 1

        second = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "Use account acct-456 and timezone UTC",
                "customer_id": "CUST-001",
                "request_id": "FD-REP-002",
                "conversation_id": first_payload["conversation_id"],
                "context": {"role": "analyst"},
            },
        )

        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["status"] == "completed"
        assert second_payload["assistant"]["intent"] == "generate_report"
        assert second_payload["assistant"]["deep_link"]
        assert second_payload["assistant"]["report_id"]
        assert second_payload["conversation_id"] == first_payload["conversation_id"]
    finally:
        app.dependency_overrides.clear()

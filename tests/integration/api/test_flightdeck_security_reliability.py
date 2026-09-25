from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.dependencies import get_flightdeck_llm_client, get_flightdeck_service
from src.api.main import app
from src.application.services.flightdeck_service import FlightdeckService
from src.infrastructure.llm.flightdeck_client import (
    ParsedFilters,
    ParsedFlightdeckIntent,
    ParsedPeriod,
)
from src.shared.configuration import get_settings
from src.shared.errors import ExternalServiceException


class _ReportReadyLLMClient:
    async def parse_intent(self, _: str) -> ParsedFlightdeckIntent:
        return ParsedFlightdeckIntent(
            intent="generate_report",
            report_type="share_of_voice",
            period=ParsedPeriod(start_date="2026-07-01", end_date="2026-07-31"),
            filters=ParsedFilters(market="US", channel="social"),
            confidence=0.95,
        )

    async def summarize_report(self, _: dict[str, object]) -> list[str]:
        return ["summary"]


class _MissingParamsLLMClient:
    async def parse_intent(self, _: str) -> ParsedFlightdeckIntent:
        return ParsedFlightdeckIntent(
            intent="generate_report",
            report_type="share_of_voice",
            period=ParsedPeriod(),
            filters=ParsedFilters(),
            confidence=0.7,
        )

    async def summarize_report(self, _: dict[str, object]) -> list[str]:
        return ["summary"]


class _FailingMCPClient:
    async def get_report_capabilities(self, role: str | None) -> dict[str, object]:
        return {
            "reports": [
                {
                    "report_type": "share_of_voice",
                    "required_params": ["account_id", "start_date", "end_date", "timezone"],
                    "optional_params": ["market", "channel", "brand"],
                    "allowed_roles": ["analyst", "manager", "admin"],
                    "enabled": role in {"analyst", "manager", "admin"} if role else True,
                }
            ]
        }

    async def get_guidance_steps(self, report_type: str) -> dict[str, object]:
        return {"report_type": report_type, "steps": ["s1"], "deep_link": "/reports/share-of-voice"}

    async def get_share_of_voice_report(self, payload: dict[str, object]) -> dict[str, object]:
        raise ExternalServiceException("Flightdeck MCP request timed out")


def test_flightdeck_rejects_role_without_permission() -> None:
    settings = get_settings()
    app.dependency_overrides[get_flightdeck_llm_client] = lambda: _ReportReadyLLMClient()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "Generate share of voice report",
                "customer_id": "CUST-001",
                "request_id": "FD-SEC-001",
                "context": {
                    "account_id": "acct-456",
                    "timezone": "UTC",
                    "role": "viewer",
                },
            },
        )

        assert response.status_code == 403
        assert "Insufficient permission" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_flightdeck_mcp_timeout_returns_safe_503() -> None:
    settings = get_settings()
    app.dependency_overrides[get_flightdeck_llm_client] = lambda: _ReportReadyLLMClient()
    app.dependency_overrides[get_flightdeck_service] = lambda: FlightdeckService(
        settings, mcp_client=_FailingMCPClient()  # type: ignore[arg-type]
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "Generate share of voice report",
                "customer_id": "CUST-001",
                "request_id": "FD-REL-001",
                "context": {
                    "account_id": "acct-456",
                    "timezone": "UTC",
                    "role": "analyst",
                },
            },
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Flightdeck MCP request timed out"
    finally:
        app.dependency_overrides.clear()


def test_flightdeck_invalid_followup_date_range_returns_400() -> None:
    settings = get_settings()
    app.dependency_overrides[get_flightdeck_llm_client] = lambda: _MissingParamsLLMClient()

    try:
        client = TestClient(app)
        first = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "I need share of voice report",
                "customer_id": "CUST-001",
                "request_id": "FD-VAL-001",
                "context": {"role": "analyst"},
            },
        )

        assert first.status_code == 200
        payload = first.json()
        assert payload["status"] == "waiting_user_input"

        second = client.post(
            "/api/flightdeck/chat",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
            json={
                "message": "Use account acct-456 timezone UTC from 2026-07-31 to 2026-07-01",
                "customer_id": "CUST-001",
                "request_id": "FD-VAL-002",
                "conversation_id": payload["conversation_id"],
                "context": {"role": "analyst"},
            },
        )

        assert second.status_code == 400
        assert second.json()["detail"] == "start_date must be <= end_date"
    finally:
        app.dependency_overrides.clear()


def test_flightdeck_invalid_api_key_is_rejected() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/flightdeck/chat",
        headers={"X-API-Key": "wrong-key", "X-Actor-Id": "integration-test"},
        json={
            "message": "I need share of voice report",
            "customer_id": "CUST-001",
            "request_id": "FD-AUTH-001",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key"

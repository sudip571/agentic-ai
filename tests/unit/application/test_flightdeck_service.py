from __future__ import annotations

import asyncio

from src.api.schemas.flightdeck import FlightdeckContext
from src.application.services.flightdeck_service import FlightdeckService
from src.shared.configuration import Settings


class _DummyMCPClient:
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
        return {
            "report_type": report_type,
            "steps": ["s1", "s2"],
            "deep_link": "/reports/share-of-voice",
        }

    async def get_share_of_voice_report(self, payload: dict[str, object]) -> dict[str, object]:
        return {"report_id": "sov-1", "metrics": {"share_percent": 10.0}, "payload": payload}


def _build_service() -> FlightdeckService:
    settings = Settings(flightdeck_ui_base_url="https://flightdeck.example.com")
    return FlightdeckService(settings, mcp_client=_DummyMCPClient())  # type: ignore[arg-type]


def test_merge_params_from_message_extracts_expected_fields() -> None:
    service = _build_service()
    params = {"timezone": "UTC"}
    merged = service.merge_params_from_message(
        params,
        "Use account acct-456 from 2026-07-01 to 2026-07-31 in us social",
    )

    assert merged["account_id"] == "acct-456"
    assert merged["start_date"] == "2026-07-01"
    assert merged["end_date"] == "2026-07-31"
    assert merged["market"] == "US"
    assert merged["channel"] == "social"


def test_build_report_link_omits_null_values_and_maps_keys() -> None:
    service = _build_service()
    link = service.build_report_link(
        {
            "account_id": "acct-456",
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "timezone": "UTC",
            "market": None,
            "channel": "social",
            "brand": None,
        }
    )

    assert link.startswith("https://flightdeck.example.com/reports/share-of-voice?")
    assert "accountId=acct-456" in link
    assert "startDate=2026-07-01" in link
    assert "endDate=2026-07-31" in link
    assert "timezone=UTC" in link
    assert "channel=social" in link
    assert "market=" not in link
    assert "brand=" not in link


def test_build_guidance_qualifies_relative_link() -> None:
    service = _build_service()

    steps, link = asyncio.run(service.build_guidance("share_of_voice"))

    assert len(steps) == 2
    assert link == "https://flightdeck.example.com/reports/share-of-voice"

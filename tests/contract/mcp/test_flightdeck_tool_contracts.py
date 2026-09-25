from __future__ import annotations

from mcp_server.services.flightdeck_service import MCPFlightdeckService


def test_flightdeck_capabilities_contract_shape() -> None:
    service = MCPFlightdeckService()

    payload = service.get_report_capabilities("analyst")

    assert set(payload.keys()) == {"reports"}
    assert isinstance(payload["reports"], list)
    assert len(payload["reports"]) == 1

    report = payload["reports"][0]
    assert set(report.keys()) == {
        "report_type",
        "required_params",
        "optional_params",
        "allowed_roles",
        "enabled",
    }
    assert report["report_type"] == "share_of_voice"
    assert report["enabled"] is True


def test_flightdeck_guidance_contract_shape() -> None:
    service = MCPFlightdeckService()

    payload = service.get_guidance_steps("share_of_voice")

    assert set(payload.keys()) == {"report_type", "steps", "deep_link"}
    assert payload["report_type"] == "share_of_voice"
    assert isinstance(payload["steps"], list)
    assert len(payload["steps"]) >= 3
    assert isinstance(payload["deep_link"], str)


def test_flightdeck_report_contract_shape() -> None:
    service = MCPFlightdeckService()

    payload = service.get_share_of_voice_report(
        tenant_id="tenant-123",
        account_id="acct-456",
        start_date="2026-07-01",
        end_date="2026-07-31",
        timezone="UTC",
        market="US",
        channel="social",
        brand="Brand A",
    )

    assert set(payload.keys()) == {
        "report_id",
        "report_type",
        "tenant_id",
        "period",
        "filters",
        "metrics",
    }
    assert payload["report_type"] == "share_of_voice"

    period = payload["period"]
    assert set(period.keys()) == {"start_date", "end_date", "timezone"}

    filters = payload["filters"]
    assert set(filters.keys()) == {"market", "channel", "brand"}

    metrics = payload["metrics"]
    assert set(metrics.keys()) == {"share_percent", "mentions", "rank", "mom_change_percent"}

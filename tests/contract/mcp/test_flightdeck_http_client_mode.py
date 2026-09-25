from __future__ import annotations

import httpx
import pytest

from src.infrastructure.mcp.flightdeck_client import FlightdeckMCPClient
from src.shared.configuration import Settings
from src.shared.errors import ExternalServiceException


def _transport() -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("X-MCP-Token") != "test-mcp-token":
            return httpx.Response(401, json={"detail": "Unauthorized"})

        if request.url.path == "/tools/fd/get_report_capabilities":
            return httpx.Response(
                200,
                json={
                    "reports": [
                        {
                            "report_type": "share_of_voice",
                            "required_params": ["account_id", "start_date", "end_date", "timezone"],
                            "optional_params": ["market", "channel", "brand"],
                            "allowed_roles": ["analyst", "manager", "admin"],
                            "enabled": True,
                        }
                    ]
                },
            )
        if request.url.path == "/tools/fd/get_guidance_steps":
            return httpx.Response(
                200,
                json={
                    "report_type": "share_of_voice",
                    "steps": ["s1", "s2", "s3"],
                    "deep_link": "/reports/share-of-voice",
                },
            )
        if request.url.path == "/tools/fd/get_share_of_voice_report":
            return httpx.Response(
                200,
                json={
                    "report_id": "sov-202607-acct-456",
                    "report_type": "share_of_voice",
                    "tenant_id": "tenant-123",
                    "period": {
                        "start_date": "2026-07-01",
                        "end_date": "2026-07-31",
                        "timezone": "UTC",
                    },
                    "filters": {"market": "US", "channel": "social", "brand": "Brand A"},
                    "metrics": {
                        "share_percent": 34.2,
                        "mentions": 12450,
                        "rank": 2,
                        "mom_change_percent": 2.1,
                    },
                },
            )
        return httpx.Response(404, json={"detail": "Not Found"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_flightdeck_http_mode_contract_calls_succeed() -> None:
    settings = Settings(
        mcp_client_mode="http",
        mcp_server_url="http://mcp.test",
        mcp_service_token="test-mcp-token",
    )
    client = FlightdeckMCPClient(settings, transport=_transport())

    capabilities = await client.get_report_capabilities("analyst")
    guidance = await client.get_guidance_steps("share_of_voice")
    report = await client.get_share_of_voice_report(
        {
            "tenant_id": "tenant-123",
            "account_id": "acct-456",
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "timezone": "UTC",
            "market": "US",
            "channel": "social",
            "brand": "Brand A",
        }
    )

    assert capabilities["reports"][0]["report_type"] == "share_of_voice"
    assert guidance["report_type"] == "share_of_voice"
    assert report["report_id"] == "sov-202607-acct-456"


@pytest.mark.asyncio
async def test_flightdeck_http_mode_rejects_invalid_token() -> None:
    settings = Settings(
        mcp_client_mode="http",
        mcp_server_url="http://mcp.test",
        mcp_service_token="wrong-token",
        mcp_retry_attempts=1,
    )
    client = FlightdeckMCPClient(settings, transport=_transport())

    with pytest.raises(ExternalServiceException):
        await client.get_report_capabilities("analyst")

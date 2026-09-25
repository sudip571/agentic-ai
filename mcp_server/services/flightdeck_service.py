from __future__ import annotations

from datetime import date
from typing import Any

from src.shared.errors import ValidationException


class MCPFlightdeckService:
    def get_report_capabilities(self, role: str | None) -> dict[str, Any]:
        allowed_roles = ["analyst", "manager", "admin"]
        return {
            "reports": [
                {
                    "report_type": "share_of_voice",
                    "required_params": ["account_id", "start_date", "end_date", "timezone"],
                    "optional_params": ["market", "channel", "brand"],
                    "allowed_roles": allowed_roles,
                    "enabled": role in allowed_roles if role else True,
                }
            ]
        }

    def get_guidance_steps(self, report_type: str) -> dict[str, Any]:
        if report_type != "share_of_voice":
            raise ValidationException("Unsupported report type")
        return {
            "report_type": report_type,
            "steps": [
                "Open Reports from the left menu.",
                "Choose Share of Voice.",
                "Set account and date range.",
                "Apply market/channel filters if needed.",
                "Click Run Report and use Export if required.",
            ],
            "deep_link": "/reports/share-of-voice",
        }

    def get_share_of_voice_report(
        self,
        tenant_id: str | None,
        account_id: str,
        start_date: str,
        end_date: str,
        timezone: str,
        market: str | None = None,
        channel: str | None = None,
        brand: str | None = None,
    ) -> dict[str, Any]:
        if not account_id:
            raise ValidationException("account_id is required")
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if start > end:
            raise ValidationException("start_date must be <= end_date")

        span_days = max((end - start).days + 1, 1)
        base_share = 30.0 + min(span_days / 31.0, 1.0) * 4.2
        metrics = {
            "share_percent": round(base_share, 2),
            "mentions": 12000 + span_days * 17,
            "rank": 2,
            "mom_change_percent": 2.1,
        }
        return {
            "report_id": f"sov-{start.strftime('%Y%m')}-{account_id}",
            "report_type": "share_of_voice",
            "tenant_id": tenant_id,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "timezone": timezone,
            },
            "filters": {
                "market": market,
                "channel": channel,
                "brand": brand,
            },
            "metrics": metrics,
        }

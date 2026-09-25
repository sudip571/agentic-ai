from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from src.api.schemas.flightdeck import FollowUpQuestion, FlightdeckContext
from src.infrastructure.llm.flightdeck_client import ParsedFlightdeckIntent
from src.infrastructure.mcp.flightdeck_client import FlightdeckMCPClient
from src.shared.configuration import Settings
from src.shared.errors import AuthorizationException, ValidationException


class FlightdeckService:
    def __init__(self, settings: Settings, mcp_client: FlightdeckMCPClient) -> None:
        self.settings = settings
        self.mcp_client = mcp_client

    async def build_guidance(self, report_type: str) -> tuple[list[str], str]:
        payload = await self.mcp_client.get_guidance_steps(report_type)
        steps = payload.get("steps", [])
        raw_link = payload.get("deep_link", "/reports/share-of-voice")
        deep_link = self._qualify_ui_link(str(raw_link))
        if not isinstance(steps, list) or not all(isinstance(x, str) for x in steps):
            raise ValidationException("Guidance payload is invalid")
        return steps, deep_link

    async def resolve_report_request(
        self,
        parsed: ParsedFlightdeckIntent,
        context: FlightdeckContext,
    ) -> tuple[dict[str, Any], list[str], list[FollowUpQuestion]]:
        params: dict[str, Any] = {
            "tenant_id": context.tenant_id,
            "account_id": context.account_id,
            "timezone": context.timezone or "UTC",
            "market": parsed.filters.market,
            "channel": parsed.filters.channel,
            "brand": parsed.filters.brand,
        }

        if parsed.period.start_date and parsed.period.end_date:
            params["start_date"] = parsed.period.start_date
            params["end_date"] = parsed.period.end_date
        elif parsed.period.month:
            month_num = self._month_to_number(parsed.period.month)
            if month_num is not None and parsed.period.year is not None:
                year = parsed.period.year
                last_day = calendar.monthrange(year, month_num)[1]
                params["start_date"] = f"{year:04d}-{month_num:02d}-01"
                params["end_date"] = f"{year:04d}-{month_num:02d}-{last_day:02d}"

        required = ["account_id", "start_date", "end_date", "timezone"]
        missing = [name for name in required if not params.get(name)]
        questions = self._build_follow_up_questions(missing)
        return params, missing, questions

    async def authorize_report_access(self, context: FlightdeckContext, report_type: str) -> None:
        capabilities = await self.mcp_client.get_report_capabilities(context.role)
        reports = capabilities.get("reports", [])
        report = next((item for item in reports if item.get("report_type") == report_type), None)
        if report is None:
            raise ValidationException(f"Unsupported report type: {report_type}")

        allowed_roles = report.get("allowed_roles", [])
        if context.role and allowed_roles and context.role not in allowed_roles:
            raise AuthorizationException("Insufficient permission for requested report")

    async def execute_share_of_voice(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self.mcp_client.get_share_of_voice_report(params)

    def build_follow_up_questions(self, missing_fields: list[str]) -> list[FollowUpQuestion]:
        return self._build_follow_up_questions(missing_fields)

    def merge_params_from_message(self, params: dict[str, Any], message: str) -> dict[str, Any]:
        merged = dict(params)
        normalized = message.lower()

        account_match = re.search(r"\b(acct-[a-z0-9-]+)\b", normalized)
        if account_match and not merged.get("account_id"):
            merged["account_id"] = account_match.group(1)

        timezone_match = re.search(r"\b(utc|asia/[a-z_]+|america/[a-z_]+|europe/[a-z_]+)\b", normalized)
        if timezone_match:
            token = timezone_match.group(1)
            merged["timezone"] = token.upper() if token == "utc" else token

        start_match = re.search(r"\b(20[0-9]{2}-[0-9]{2}-[0-9]{2})\b", normalized)
        if start_match and not merged.get("start_date"):
            merged["start_date"] = start_match.group(1)

        date_matches = re.findall(r"\b(20[0-9]{2}-[0-9]{2}-[0-9]{2})\b", normalized)
        if len(date_matches) >= 2:
            merged["start_date"] = date_matches[0]
            merged["end_date"] = date_matches[1]

        if merged.get("start_date") and not merged.get("end_date"):
            if "end" in normalized or "to" in normalized:
                second_match = re.search(r"(?:end|to)\s+(20[0-9]{2}-[0-9]{2}-[0-9]{2})", normalized)
                if second_match:
                    merged["end_date"] = second_match.group(1)

        for market in ["US", "UK", "IN", "CA", "AU"]:
            if re.search(rf"\b{market.lower()}\b", normalized):
                merged["market"] = market
                break

        for channel in ["social", "news", "search", "video"]:
            if channel in normalized:
                merged["channel"] = channel
                break

        return merged

    def build_report_link(self, params: dict[str, Any]) -> str:
        allow_list = ["account_id", "start_date", "end_date", "timezone", "market", "channel", "brand"]
        query_payload = {self._to_query_key(k): v for k, v in params.items() if k in allow_list and v}
        query = urlencode(query_payload)
        base = self._qualify_ui_link("/reports/share-of-voice")
        return f"{base}?{query}" if query else base

    def _month_to_number(self, month: str) -> int | None:
        lookup = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }
        return lookup.get(month.lower())

    def _build_follow_up_questions(self, missing_fields: list[str]) -> list[FollowUpQuestion]:
        prompts = {
            "account_id": FollowUpQuestion(
                id="account_id",
                question="Which account should I use for the report?",
                examples=["acct-456"],
            ),
            "start_date": FollowUpQuestion(
                id="start_date",
                question="What start date should I use? (YYYY-MM-DD)",
                examples=[f"{datetime.now(UTC).year}-07-01"],
            ),
            "end_date": FollowUpQuestion(
                id="end_date",
                question="What end date should I use? (YYYY-MM-DD)",
                examples=[f"{datetime.now(UTC).year}-07-31"],
            ),
            "timezone": FollowUpQuestion(
                id="timezone",
                question="Which timezone should I use?",
                examples=["UTC", "Asia/Kathmandu"],
            ),
        }
        return [prompts[key] for key in missing_fields if key in prompts]

    def _qualify_ui_link(self, path: str) -> str:
        base = self.settings.flightdeck_ui_base_url.rstrip("/")
        if path.startswith("http://") or path.startswith("https://"):
            return path
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{base}{suffix}"

    def _to_query_key(self, snake_case: str) -> str:
        mapping = {
            "account_id": "accountId",
            "start_date": "startDate",
            "end_date": "endDate",
        }
        return mapping.get(snake_case, snake_case)

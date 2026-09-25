from __future__ import annotations

import re
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from litellm import acompletion
from pydantic import BaseModel, Field

from src.shared.configuration import Settings
from src.shared.observability import record_llm_result


class ParsedPeriod(BaseModel):
    month: str | None = None
    year: int | None = None
    start_date: str | None = None
    end_date: str | None = None


class ParsedFilters(BaseModel):
    market: str | None = None
    channel: str | None = None
    brand: str | None = None


class ParsedFlightdeckIntent(BaseModel):
    intent: str = Field(default="unknown")
    report_type: str | None = None
    period: ParsedPeriod = Field(default_factory=ParsedPeriod)
    filters: ParsedFilters = Field(default_factory=ParsedFilters)
    format: str = Field(default="summary_only")
    confidence: float = Field(default=0.0)


class FlightdeckLLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._intent_parser: PydanticOutputParser[ParsedFlightdeckIntent]
        self._intent_prompt: ChatPromptTemplate
        self._intent_parser = PydanticOutputParser(pydantic_object=ParsedFlightdeckIntent)
        self._intent_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a Flightdeck assistant parser. "
                    "Classify intent and extract parameters. "
                    "Never infer permissions or execute actions. "
                    "Return JSON only.\n{format_instructions}",
                ),
                ("human", "{message}"),
            ]
        )

    async def parse_intent(self, message: str) -> ParsedFlightdeckIntent:
        started_at = perf_counter()
        try:
            prompt_messages = self._intent_prompt.format_messages(
                message=message,
                format_instructions=self._intent_parser.get_format_instructions(),
            )
            litellm_messages = [
                {
                    "role": "user" if msg.type == "human" else msg.type,
                    "content": msg.content,
                }
                for msg in prompt_messages
            ]
            response = await acompletion(
                model=self.settings.llm_model,
                base_url=self.settings.litellm_base_url,
                api_key=self.settings.litellm_api_key,
                timeout=self.settings.llm_timeout_seconds,
                messages=litellm_messages,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty LLM response")
            parsed = self._intent_parser.parse(content)
            usage = cast(Any, getattr(response, "usage", None))
            prompt_tokens = cast(int | None, getattr(usage, "prompt_tokens", None))
            completion_tokens = cast(int | None, getattr(usage, "completion_tokens", None))
            total_tokens = cast(int | None, getattr(usage, "total_tokens", None))
            record_llm_result(
                "success",
                perf_counter() - started_at,
                prompt_tokens,
                completion_tokens,
                total_tokens,
            )
            return ParsedFlightdeckIntent.model_validate(parsed.model_dump())
        except Exception:
            record_llm_result("failure", perf_counter() - started_at, None, None, None)
            return self._fallback_parse(message)

    async def summarize_report(self, report_payload: dict[str, Any]) -> list[str]:
        metrics = cast(dict[str, Any], report_payload.get("metrics", {}))
        share = metrics.get("share_percent")
        change = metrics.get("mom_change_percent")
        rank = metrics.get("rank")
        summary = [
            f"Share of voice: {share}%" if share is not None else "Share of voice unavailable",
            (
                f"Month-over-month change: {change}%"
                if change is not None
                else "Month-over-month change unavailable"
            ),
            f"Rank: {rank}" if rank is not None else "Rank unavailable",
        ]
        return summary

    def _fallback_parse(self, message: str) -> ParsedFlightdeckIntent:
        normalized = message.lower()
        intent = "unknown"
        if "how to use" in normalized or "how do i" in normalized:
            intent = "guidance"
        elif "report" in normalized or "reporting" in normalized:
            intent = "generate_report"

        report_type = "share_of_voice" if "share of voice" in normalized else None

        month = None
        for name in [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]:
            if name in normalized:
                month = name
                break

        year_match = re.search(r"\b(20[0-9]{2})\b", normalized)
        year = int(year_match.group(1)) if year_match else None
        if month and year is None and intent == "generate_report":
            year = datetime.now(UTC).year

        market = None
        market_match = re.search(r"\bin\s+(us|uk|in|ca|au)\b", normalized)
        if market_match:
            market = market_match.group(1).upper()

        channel = None
        for candidate in ["social", "news", "search", "video"]:
            if candidate in normalized:
                channel = candidate
                break

        return ParsedFlightdeckIntent(
            intent=intent,
            report_type=report_type,
            period=ParsedPeriod(month=month, year=year),
            filters=ParsedFilters(market=market, channel=channel),
            format="summary_only",
            confidence=0.4,
        )

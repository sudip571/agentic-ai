from __future__ import annotations

from typing import Any, TypedDict

from src.api.schemas.flightdeck import FlightdeckAssistantPayload, FlightdeckContext, FollowUpQuestion
from src.infrastructure.llm.flightdeck_client import ParsedFlightdeckIntent


class FlightdeckAgentState(TypedDict, total=False):
    request_id: str
    workflow_id: str
    conversation_id: str
    user_message: str
    customer_id: str
    context: FlightdeckContext
    parsed: ParsedFlightdeckIntent
    missing_fields: list[str]
    follow_up_questions: list[FollowUpQuestion]
    report_params: dict[str, Any]
    report_payload: dict[str, Any]
    deep_link: str
    assistant: FlightdeckAssistantPayload
    status: str
    response_message: str
    error: str

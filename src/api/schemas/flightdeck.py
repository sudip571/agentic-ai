from __future__ import annotations

from pydantic import BaseModel, Field


class FlightdeckContext(BaseModel):
    tenant_id: str | None = Field(default=None, min_length=2, max_length=128)
    account_id: str | None = Field(default=None, min_length=2, max_length=128)
    timezone: str | None = Field(default=None, min_length=2, max_length=64)
    locale: str | None = Field(default=None, min_length=2, max_length=32)
    role: str | None = Field(default=None, min_length=2, max_length=64)


class FlightdeckChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    customer_id: str = Field(..., pattern=r"^CUST-[0-9]{3,}$")
    request_id: str | None = Field(default=None, max_length=64)
    conversation_id: str | None = Field(default=None, min_length=3, max_length=64)
    context: FlightdeckContext | None = None


class FollowUpQuestion(BaseModel):
    id: str
    question: str
    examples: list[str] = Field(default_factory=list)


class FlightdeckAssistantPayload(BaseModel):
    intent: str
    report_type: str | None = None
    summary: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list)
    deep_link: str | None = None
    report_id: str | None = None


class FlightdeckChatResponse(BaseModel):
    request_id: str
    workflow_id: str
    conversation_id: str
    status: str
    message: str
    assistant: FlightdeckAssistantPayload

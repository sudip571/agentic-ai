from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import cast
from uuid import uuid4

from src.agent.flightdeck_state import FlightdeckAgentState
from src.api.schemas.flightdeck import FlightdeckAssistantPayload, FlightdeckContext
from src.application.services.flightdeck_conversation_store import (
    PendingFlightdeckRequest,
    conversation_store,
)
from src.application.services.flightdeck_service import FlightdeckService
from src.infrastructure.llm.flightdeck_client import FlightdeckLLMClient
from src.shared.observability import record_workflow_result


class FlightdeckWorkflow:
    def __init__(self, service: FlightdeckService, llm_client: FlightdeckLLMClient) -> None:
        self.service = service
        self.llm_client = llm_client

    async def run(
        self,
        message: str,
        customer_id: str,
        context: FlightdeckContext | None = None,
        request_id: str | None = None,
        conversation_id: str | None = None,
    ) -> FlightdeckAgentState:
        started_at = perf_counter()
        workflow_id = str(uuid4())
        conv_id = conversation_id or str(uuid4())
        state: FlightdeckAgentState = {
            "request_id": request_id or str(uuid4()),
            "workflow_id": workflow_id,
            "conversation_id": conv_id,
            "user_message": message,
            "customer_id": customer_id,
            "context": context or FlightdeckContext(),
        }

        try:
            parsed = await self.llm_client.parse_intent(message)
            state["parsed"] = parsed
            report_type = parsed.report_type or "share_of_voice"
            pending = conversation_store.get(conv_id)

            if parsed.intent == "guidance" and pending is None:
                steps, deep_link = await self.service.build_guidance(report_type)
                state["status"] = "completed"
                state["response_message"] = "Here is how to use share of voice reporting."
                state["assistant"] = FlightdeckAssistantPayload(
                    intent="guidance",
                    report_type=report_type,
                    steps=steps,
                    deep_link=deep_link,
                )
                record_workflow_result("completed", perf_counter() - started_at)
                return state

            if pending is not None:
                report_type = pending.report_type
                context_value = state["context"]
                merged = dict(pending.params)
                if context_value.account_id and not merged.get("account_id"):
                    merged["account_id"] = context_value.account_id
                if context_value.timezone and not merged.get("timezone"):
                    merged["timezone"] = context_value.timezone
                merged = self.service.merge_params_from_message(merged, message)

                missing = [name for name in pending.missing_fields if not merged.get(name)]
                if missing:
                    questions = self.service.build_follow_up_questions(missing)
                    conversation_store.save(
                        PendingFlightdeckRequest(
                            conversation_id=conv_id,
                            report_type=report_type,
                            params=merged,
                            missing_fields=missing,
                            updated_at=datetime.now(UTC),
                        )
                    )
                    state["status"] = "waiting_user_input"
                    state["response_message"] = "I still need a few details before I can run this report."
                    state["assistant"] = FlightdeckAssistantPayload(
                        intent="generate_report",
                        report_type=report_type,
                        follow_up_questions=questions,
                    )
                    record_workflow_result("waiting_user_input", perf_counter() - started_at)
                    return state

                await self.service.authorize_report_access(context_value, report_type)
                report_payload = await self.service.execute_share_of_voice(merged)
                summary = await self.llm_client.summarize_report(report_payload)
                deep_link = self.service.build_report_link(merged)
                conversation_store.delete(conv_id)
                state["report_payload"] = report_payload
                state["deep_link"] = deep_link
                state["status"] = "completed"
                state["response_message"] = "Share of voice report generated."
                state["assistant"] = FlightdeckAssistantPayload(
                    intent="generate_report",
                    report_type=report_type,
                    summary=summary,
                    deep_link=deep_link,
                    report_id=cast(str | None, report_payload.get("report_id")),
                )
                record_workflow_result("completed", perf_counter() - started_at)
                return state

            if parsed.intent != "generate_report" or report_type != "share_of_voice":
                state["status"] = "completed"
                state["response_message"] = "I can help with share of voice guidance or reporting."
                state["assistant"] = FlightdeckAssistantPayload(
                    intent="unknown",
                    report_type=report_type,
                    follow_up_questions=[],
                )
                record_workflow_result("completed", perf_counter() - started_at)
                return state

            context_value = state["context"]
            params, missing, questions = await self.service.resolve_report_request(parsed, context_value)
            state["report_params"] = params

            if missing:
                conversation_store.save(
                    PendingFlightdeckRequest(
                        conversation_id=conv_id,
                        report_type=report_type,
                        params=params,
                        missing_fields=missing,
                        updated_at=datetime.now(UTC),
                    )
                )
                state["status"] = "waiting_user_input"
                state["response_message"] = "I need a few details before I can run this report."
                state["assistant"] = FlightdeckAssistantPayload(
                    intent="generate_report",
                    report_type=report_type,
                    follow_up_questions=questions,
                )
                record_workflow_result("waiting_user_input", perf_counter() - started_at)
                return state

            await self.service.authorize_report_access(context_value, report_type)
            report_payload = await self.service.execute_share_of_voice(params)
            summary = await self.llm_client.summarize_report(report_payload)
            deep_link = self.service.build_report_link(params)
            conversation_store.delete(conv_id)
            state["report_payload"] = report_payload
            state["deep_link"] = deep_link
            state["status"] = "completed"
            state["response_message"] = "Share of voice report generated."
            state["assistant"] = FlightdeckAssistantPayload(
                intent="generate_report",
                report_type=report_type,
                summary=summary,
                deep_link=deep_link,
                report_id=cast(str | None, report_payload.get("report_id")),
            )
            record_workflow_result("completed", perf_counter() - started_at)
            return state
        except Exception:
            record_workflow_result("failed", perf_counter() - started_at)
            raise

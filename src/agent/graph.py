from __future__ import annotations

import json
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.understand_request import understand_request
from src.agent.state import BillingAgentState
from src.application.services.billing_service import BillingService
from src.domain.enums.billing_status import BillingDecision
from src.infrastructure.email.service import EmailService
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.persistence.repositories.billing_repository import BillingRepository
from src.shared.logging import get_logger
from src.shared.observability import record_workflow_result

logger = get_logger(__name__)


class BillingWorkflow:
    def __init__(
        self, billing_service: BillingService, llm_client: LLMClient, email_service: EmailService
    ) -> None:
        self.billing_service = billing_service
        self.llm_client = llm_client
        self.email_service = email_service

    def _build_graph(self) -> Any:
        graph = StateGraph(BillingAgentState)

        async def understand(state: BillingAgentState) -> BillingAgentState:
            return await understand_request(state, self.llm_client)

        async def evaluate(state: BillingAgentState) -> BillingAgentState:
            session: AsyncSession = state["session"]
            repo, calc, invoice_id, currency = await self.billing_service.analyze_customer_billing(
                session=session,
                request_id=state["request_id"],
                workflow_id=state["workflow_id"],
                customer_id=state["customer_id"],
            )
            await repo.upsert_workflow_state(
                state["workflow_id"],
                state["request_id"],
                "EVALUATED",
                json.dumps(
                    {
                        "decision": calc.decision.value,
                        "invoice_id": invoice_id,
                        "currency": currency,
                    }
                ),
            )
            await session.commit()
            return {
                **state,
                "discrepancy": calc.discrepancy,
                "decision": calc.decision,
                "decision_reason": calc.reason,
                "invoice_id": invoice_id,
                "currency": currency,
            }

        async def side_effects(state: BillingAgentState) -> BillingAgentState:
            session: AsyncSession = state["session"]
            repo = BillingRepository(session)
            decision = state["decision"]
            if decision == BillingDecision.AUTO_CREDIT:
                credit_id = await self.billing_service.create_credit_if_allowed(
                    repo=repo,
                    request_id=state["request_id"],
                    customer_id=state["customer_id"],
                    invoice_id=state["invoice_id"],
                    discrepancy=state["discrepancy"],
                    currency=state["currency"],
                )
                await repo.upsert_workflow_state(
                    state["workflow_id"],
                    state["request_id"],
                    "COMPLETED",
                    json.dumps({"credit_id": credit_id}),
                )
                await self.email_service.send_notification(
                    state["customer_id"], f"A credit of {state['discrepancy']} has been issued."
                )
                await session.commit()
                return {
                    **state,
                    "status": "completed",
                    "credit_id": credit_id,
                    "response_message": f"We issued a credit of {state['discrepancy']}.",
                }

            if decision == BillingDecision.HUMAN_APPROVAL:
                approval_id = await self.billing_service.create_approval_request(
                    repo=repo,
                    request_id=state["request_id"],
                    workflow_id=state["workflow_id"],
                    customer_id=state["customer_id"],
                    invoice_id=state["invoice_id"],
                    discrepancy=state["discrepancy"],
                    currency=state["currency"],
                )
                await repo.upsert_workflow_state(
                    state["workflow_id"],
                    state["request_id"],
                    "WAITING_APPROVAL",
                    json.dumps({"approval_id": approval_id}),
                )
                await session.commit()
                return {
                    **state,
                    "status": "waiting_approval",
                    "approval_request_id": approval_id,
                    "response_message": "Discrepancy requires human approval.",
                }

            await repo.upsert_workflow_state(
                state["workflow_id"],
                state["request_id"],
                "COMPLETED",
                json.dumps({"decision": decision.value}),
            )
            await session.commit()
            return {
                **state,
                "status": "completed",
                "response_message": f"Request reviewed: {state['decision_reason']}",
            }

        graph.add_node("understand", understand)
        graph.add_node("evaluate", evaluate)
        graph.add_node("side_effects", side_effects)
        graph.add_edge(START, "understand")
        graph.add_edge("understand", "evaluate")
        graph.add_edge("evaluate", "side_effects")
        graph.add_edge("side_effects", END)
        return graph.compile()

    async def run(
        self, session: AsyncSession, message: str, customer_id: str, request_id: str | None = None
    ) -> BillingAgentState:
        workflow_id = str(uuid4())
        state: BillingAgentState = {
            "session": session,
            "request_id": request_id or str(uuid4()),
            "workflow_id": workflow_id,
            "user_message": message,
            "customer_id": customer_id,
        }
        graph = self._build_graph()
        started_at = perf_counter()
        try:
            result = await graph.ainvoke(state)
            outcome = str(result.get("status", "completed"))
            record_workflow_result(outcome, perf_counter() - started_at)
            logger.info(
                "workflow_completed",
                workflow_id=workflow_id,
                request_id=result["request_id"],
            )
            return cast(BillingAgentState, result)
        except Exception:
            record_workflow_result("failed", perf_counter() - started_at)
            raise

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.graph import BillingWorkflow
from src.api.dependencies import (
    authorize,
    get_billing_service,
    get_email_service,
    get_llm_client,
    get_session,
)
from src.api.rate_limit import rate_limit_approval, rate_limit_chat
from src.api.schemas.chat import ApprovalActionRequest, ChatRequest, ChatResponse
from src.application.interfaces.auth import Permission
from src.application.services.billing_service import BillingService
from src.infrastructure.email.service import EmailService
from src.infrastructure.llm.client import LLMClient

router = APIRouter(prefix="/api", tags=["billing"])

WRITE_AUTH_DEP = Depends(authorize(Permission.WRITE))
APPROVE_AUTH_DEP = Depends(authorize(Permission.APPROVE))
BILLING_SERVICE_DEP = Depends(get_billing_service)
LLM_CLIENT_DEP = Depends(get_llm_client)
EMAIL_SERVICE_DEP = Depends(get_email_service)
SESSION_DEP = Depends(get_session)
CHAT_RATE_LIMIT_DEP = Depends(rate_limit_chat)
APPROVAL_RATE_LIMIT_DEP = Depends(rate_limit_approval)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    _: object = WRITE_AUTH_DEP,
    __: None = CHAT_RATE_LIMIT_DEP,
    billing_service: BillingService = BILLING_SERVICE_DEP,
    llm_client: LLMClient = LLM_CLIENT_DEP,
    email_service: EmailService = EMAIL_SERVICE_DEP,
    session: AsyncSession = SESSION_DEP,
) -> ChatResponse:
    workflow = BillingWorkflow(billing_service, llm_client, email_service)
    state = await workflow.run(session, req.message, req.customer_id, req.request_id)
    return ChatResponse(
        request_id=state["request_id"],
        workflow_id=state["workflow_id"],
        status=state.get("status", "completed"),
        message=state.get("response_message", "Request processed"),
        requires_human_approval=state.get("status") == "waiting_approval",
        approval_request_id=state.get("approval_request_id"),
    )


@router.post("/approvals/{approval_id}/decision", response_model=ChatResponse)
async def approval_decision(
    approval_id: str,
    req: ApprovalActionRequest,
    _: object = APPROVE_AUTH_DEP,
    __: None = APPROVAL_RATE_LIMIT_DEP,
    billing_service: BillingService = BILLING_SERVICE_DEP,
    email_service: EmailService = EMAIL_SERVICE_DEP,
    session: AsyncSession = SESSION_DEP,
) -> ChatResponse:
    result = await billing_service.process_approval(
        session=session,
        approval_id=approval_id,
        decision=req.decision,
        approver_id=req.approver_id,
    )
    await session.commit()
    if result.outcome == "approved":
        await email_service.send_notification(
            result.customer_id,
            f"Your billing approval was completed and a credit of {result.amount} was issued.",
        )
    else:
        await email_service.send_notification(
            result.customer_id,
            "Your billing approval request was rejected.",
        )

    return ChatResponse(
        request_id=result.request_id,
        workflow_id=result.workflow_id,
        status="completed",
        message=f"Approval {result.outcome}.",
        requires_human_approval=False,
    )

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.agent.flightdeck_graph import FlightdeckWorkflow
from src.api.dependencies import authorize, get_flightdeck_llm_client, get_flightdeck_service
from src.api.rate_limit import rate_limit_chat
from src.api.schemas.flightdeck import FlightdeckChatRequest, FlightdeckChatResponse
from src.application.interfaces.auth import Permission
from src.application.services.flightdeck_service import FlightdeckService
from src.infrastructure.llm.flightdeck_client import FlightdeckLLMClient

router = APIRouter(prefix="/api/flightdeck", tags=["flightdeck"])

WRITE_AUTH_DEP = Depends(authorize(Permission.WRITE))
CHAT_RATE_LIMIT_DEP = Depends(rate_limit_chat)
FLIGHTDECK_SERVICE_DEP = Depends(get_flightdeck_service)
FLIGHTDECK_LLM_DEP = Depends(get_flightdeck_llm_client)


@router.post("/chat", response_model=FlightdeckChatResponse)
async def flightdeck_chat(
    req: FlightdeckChatRequest,
    _: object = WRITE_AUTH_DEP,
    __: None = CHAT_RATE_LIMIT_DEP,
    service: FlightdeckService = FLIGHTDECK_SERVICE_DEP,
    llm_client: FlightdeckLLMClient = FLIGHTDECK_LLM_DEP,
) -> FlightdeckChatResponse:
    workflow = FlightdeckWorkflow(service, llm_client)
    state = await workflow.run(
        message=req.message,
        customer_id=req.customer_id,
        context=req.context,
        request_id=req.request_id,
        conversation_id=req.conversation_id,
    )
    return FlightdeckChatResponse(
        request_id=state["request_id"],
        workflow_id=state["workflow_id"],
        conversation_id=state["conversation_id"],
        status=state.get("status", "completed"),
        message=state.get("response_message", "Request processed"),
        assistant=state["assistant"],
    )

from __future__ import annotations

from src.agent.state import BillingAgentState
from src.infrastructure.llm.client import LLMClient


async def understand_request(state: BillingAgentState, llm_client: LLMClient) -> BillingAgentState:
    parsed = await llm_client.parse_request(state["user_message"])
    response = "Billing request understood. "
    if parsed.claimed_amount is not None and parsed.expected_amount is not None:
        response += (
            f"Claimed amount is {parsed.claimed_amount} "
            f"and expected amount is {parsed.expected_amount}."
        )
    return {**state, "response_message": response}

from __future__ import annotations

from decimal import Decimal

import pytest

from src.infrastructure.llm.client import LLMClient
from src.shared.configuration import Settings


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


@pytest.mark.asyncio
async def test_parse_request_uses_langchain_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_acompletion(**_: object) -> _Response:
        return _Response(
            '{"claimed_amount": 150, "expected_amount": 100, "requested_action": "investigate"}'
        )

    monkeypatch.setattr("src.infrastructure.llm.client.acompletion", fake_acompletion)

    client = LLMClient(Settings())
    parsed = await client.parse_request("My bill is $150 but should be $100")

    assert parsed.claimed_amount == Decimal("150")
    assert parsed.expected_amount == Decimal("100")
    assert parsed.requested_action == "investigate"


@pytest.mark.asyncio
async def test_parse_request_falls_back_to_regex_when_llm_output_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_acompletion(**_: object) -> _Response:
        return _Response("not valid json")

    monkeypatch.setattr("src.infrastructure.llm.client.acompletion", fake_acompletion)

    client = LLMClient(Settings())
    parsed = await client.parse_request("My bill is $150 but should be $100")

    assert parsed.claimed_amount == Decimal("150")
    assert parsed.expected_amount == Decimal("100")
    assert parsed.requested_action == "investigate"

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.main import app
from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.models import (
    ApprovalRequestTable,
    CreditTable,
    WorkflowRunTable,
)
from src.infrastructure.persistence.seed import seed
from src.shared.configuration import get_settings


def _build_client() -> TestClient:
    return TestClient(app)


def _fetch_approval(approval_id: str) -> ApprovalRequestTable | None:
    async def _run() -> ApprovalRequestTable | None:
        db = Database(get_settings())
        async for session in db.get_session():
            return await session.get(ApprovalRequestTable, approval_id)
        return None

    return asyncio.run(_run())


def _set_expired(approval_id: str) -> None:
    async def _run() -> None:
        db = Database(get_settings())
        async for session in db.get_session():
            row = await session.get(ApprovalRequestTable, approval_id)
            if row is None:
                return
            row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await session.commit()
            return

    asyncio.run(_run())


def _count_credits_by_request(request_id: str) -> int:
    async def _run() -> int:
        db = Database(get_settings())
        async for session in db.get_session():
            rows = (
                (
                    await session.execute(
                        select(CreditTable).where(CreditTable.request_id == request_id)
                    )
                )
                .scalars()
                .all()
            )
            return len(rows)
        return 0

    return asyncio.run(_run())


def _workflow_status(workflow_id: str) -> str | None:
    async def _run() -> str | None:
        db = Database(get_settings())
        async for session in db.get_session():
            row = await session.get(WorkflowRunTable, workflow_id)
            return None if row is None else row.status
        return None

    return asyncio.run(_run())


def _create_waiting_approval(client: TestClient, request_id: str) -> dict[str, Any]:
    settings = get_settings()
    response = client.post(
        "/api/chat",
        headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "integration-test"},
        json={
            "message": "My bill is $150 but should be $100",
            "customer_id": "CUST-001",
            "request_id": request_id,
        },
    )
    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["requires_human_approval"] is True
    assert payload["approval_request_id"]
    return payload


def test_approval_decision_approve_resumes_and_creates_credit() -> None:
    asyncio.run(seed())
    request_id = f"REQ-APPROVE-{uuid4()}"
    settings = get_settings()

    with _build_client() as client:
        created = _create_waiting_approval(client, request_id)

        response = client.post(
            f"/api/approvals/{created['approval_request_id']}/decision",
            headers={"X-API-Key": settings.auth_approve_key, "X-Actor-Id": "approver-1"},
            json={"approver_id": "approver-1", "decision": "approve"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert _count_credits_by_request(request_id) == 1
    assert _workflow_status(created["workflow_id"]) == "COMPLETED"


def test_approval_decision_reject_marks_completed_without_credit() -> None:
    asyncio.run(seed())
    request_id = f"REQ-REJECT-{uuid4()}"
    settings = get_settings()

    with _build_client() as client:
        created = _create_waiting_approval(client, request_id)

        response = client.post(
            f"/api/approvals/{created['approval_request_id']}/decision",
            headers={"X-API-Key": settings.auth_approve_key, "X-Actor-Id": "approver-2"},
            json={"approver_id": "approver-2", "decision": "reject"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Approval rejected."
    assert _count_credits_by_request(request_id) == 0
    assert _workflow_status(created["workflow_id"]) == "COMPLETED"


def test_approval_decision_duplicate_is_rejected() -> None:
    asyncio.run(seed())
    request_id = f"REQ-DUP-APPROVAL-{uuid4()}"
    settings = get_settings()

    with _build_client() as client:
        created = _create_waiting_approval(client, request_id)

        first = client.post(
            f"/api/approvals/{created['approval_request_id']}/decision",
            headers={"X-API-Key": settings.auth_approve_key, "X-Actor-Id": "approver-3"},
            json={"approver_id": "approver-3", "decision": "approve"},
        )
        second = client.post(
            f"/api/approvals/{created['approval_request_id']}/decision",
            headers={"X-API-Key": settings.auth_approve_key, "X-Actor-Id": "approver-3"},
            json={"approver_id": "approver-3", "decision": "approve"},
        )

    assert first.status_code == 200
    assert second.status_code == 409


def test_approval_decision_expired_is_rejected() -> None:
    asyncio.run(seed())
    request_id = f"REQ-EXPIRED-{uuid4()}"
    settings = get_settings()

    with _build_client() as client:
        created = _create_waiting_approval(client, request_id)
        approval_id = created["approval_request_id"]

    _set_expired(approval_id)

    with _build_client() as client:
        response = client.post(
            f"/api/approvals/{approval_id}/decision",
            headers={"X-API-Key": settings.auth_approve_key, "X-Actor-Id": "approver-4"},
            json={"approver_id": "approver-4", "decision": "approve"},
        )

    assert response.status_code == 400


def test_approval_decision_unauthorized_user_is_rejected() -> None:
    asyncio.run(seed())
    request_id = f"REQ-UNAUTH-{uuid4()}"
    settings = get_settings()

    with _build_client() as client:
        created = _create_waiting_approval(client, request_id)

        response = client.post(
            f"/api/approvals/{created['approval_request_id']}/decision",
            headers={"X-API-Key": settings.auth_write_key, "X-Actor-Id": "writer-user"},
            json={"approver_id": "writer-user", "decision": "approve"},
        )

    assert response.status_code == 403

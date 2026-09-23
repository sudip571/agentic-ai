from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEvent(BaseModel):
    event_id: str
    request_id: str
    workflow_id: str
    event_type: str
    timestamp: datetime
    actor: str
    source: str
    metadata: dict[str, Any]

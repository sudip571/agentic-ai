from __future__ import annotations

from src.shared.logging import get_logger


class EmailService:
    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    async def send_notification(self, customer_id: str, message: str) -> None:
        self.logger.info("email_notification_sent", customer_id=customer_id, message=message)

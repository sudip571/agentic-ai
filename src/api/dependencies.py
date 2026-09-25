from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.interfaces.auth import Permission
from src.application.services.billing_service import BillingService
from src.application.services.flightdeck_service import FlightdeckService
from src.infrastructure.email.service import EmailService
from src.infrastructure.llm.flightdeck_client import FlightdeckLLMClient
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.mcp.client import BillingMCPClient
from src.infrastructure.mcp.flightdeck_client import FlightdeckMCPClient
from src.infrastructure.persistence.database import Database
from src.infrastructure.security.identity_provider import OIDCIntrospectionIdentityProvider
from src.shared.configuration import Settings, get_settings
from src.shared.errors import AuthorizationException


@dataclass(frozen=True)
class CallerContext:
    actor_id: str
    permission: Permission


def _resolve_permission(api_key: str, settings: Settings) -> Permission:
    if api_key == settings.auth_read_key:
        return Permission.READ
    if api_key == settings.auth_write_key:
        return Permission.WRITE
    if api_key == settings.auth_approve_key:
        return Permission.APPROVE
    if api_key == settings.auth_admin_key:
        return Permission.ADMIN
    raise AuthorizationException("Invalid API key")


def _permission_hierarchy() -> dict[Permission, int]:
    return {
        Permission.READ: 1,
        Permission.WRITE: 2,
        Permission.APPROVE: 3,
        Permission.ADMIN: 4,
    }


def _parse_bearer_token(authorization: str) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthorizationException("Invalid Authorization header")
    return token


def authorize(required: Permission) -> Callable[..., Awaitable[CallerContext]]:
    async def _dep(
        x_api_key: str = Header(default="", alias="X-API-Key"),
        x_actor_id: str = Header(default="system", alias="X-Actor-Id"),
        authorization: str = Header(default="", alias="Authorization"),
    ) -> CallerContext:
        settings = get_settings()
        hierarchy = _permission_hierarchy()

        if settings.auth_mode == "oidc_introspection":
            token = _parse_bearer_token(authorization)
            provider = get_identity_provider()
            identity = await provider.authenticate(token)
            permission = identity.permission
            actor_id = x_actor_id if x_actor_id != "system" else identity.subject
            if hierarchy[permission] < hierarchy[required]:
                raise AuthorizationException("Insufficient permission")
            return CallerContext(actor_id=actor_id, permission=permission)

        permission = _resolve_permission(x_api_key, settings)
        if hierarchy[permission] < hierarchy[required]:
            raise AuthorizationException("Insufficient permission")
        return CallerContext(actor_id=x_actor_id, permission=permission)

    return _dep


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database(get_settings())


@lru_cache(maxsize=1)
def get_identity_provider() -> OIDCIntrospectionIdentityProvider:
    return OIDCIntrospectionIdentityProvider(get_settings())


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    database = get_database()
    async for session in database.get_session():
        yield session


def get_billing_service() -> BillingService:
    settings = get_settings()
    return BillingService(settings, mcp_client=BillingMCPClient(settings))


def get_llm_client() -> LLMClient:
    return LLMClient(get_settings())


def get_flightdeck_llm_client() -> FlightdeckLLMClient:
    return FlightdeckLLMClient(get_settings())


def get_flightdeck_service() -> FlightdeckService:
    settings = get_settings()
    return FlightdeckService(settings, mcp_client=FlightdeckMCPClient(settings))


def get_email_service() -> EmailService:
    return EmailService()

from __future__ import annotations

import httpx
import pytest

from src.application.interfaces.auth import Permission
from src.infrastructure.security.identity_provider import OIDCIntrospectionIdentityProvider
from src.shared.configuration import Settings
from src.shared.errors import AuthorizationException


def _settings() -> Settings:
    return Settings(
        auth_mode="oidc_introspection",
        auth_introspection_url="https://idp.example.com/oauth2/introspect",
        auth_introspection_client_id="billing-agent",
        auth_introspection_client_secret="secret",
    )


@pytest.mark.asyncio
async def test_oidc_identity_provider_maps_write_role_to_permission() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "active": True,
                "sub": "user-123",
                "roles": ["billing.write"],
            },
        )

    provider = OIDCIntrospectionIdentityProvider(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    identity = await provider.authenticate("token-abc")

    assert identity.subject == "user-123"
    assert identity.permission == Permission.WRITE


@pytest.mark.asyncio
async def test_oidc_identity_provider_rejects_inactive_token() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"active": False})

    provider = OIDCIntrospectionIdentityProvider(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AuthorizationException):
        await provider.authenticate("inactive-token")

from __future__ import annotations

import pytest

from src.api.dependencies import authorize
from src.application.interfaces.auth import Permission
from src.infrastructure.security.identity_provider import IdentityContext
from src.shared.configuration import Settings
from src.shared.errors import AuthorizationException


class _FakeIdentityProvider:
    def __init__(self, permission: Permission) -> None:
        self._permission = permission

    async def authenticate(self, _: str) -> IdentityContext:
        return IdentityContext(subject="enterprise-user", permission=self._permission)


@pytest.mark.asyncio
async def test_authorize_uses_oidc_introspection_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(auth_mode="oidc_introspection")

    monkeypatch.setattr("src.api.dependencies.get_settings", lambda: settings)
    monkeypatch.setattr(
        "src.api.dependencies.get_identity_provider",
        lambda: _FakeIdentityProvider(Permission.APPROVE),
    )

    dep = authorize(Permission.WRITE)
    caller = await dep(authorization="Bearer token-123", x_api_key="", x_actor_id="system")

    assert caller.permission == Permission.APPROVE
    assert caller.actor_id == "enterprise-user"


@pytest.mark.asyncio
async def test_authorize_rejects_invalid_bearer_header(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(auth_mode="oidc_introspection")
    monkeypatch.setattr("src.api.dependencies.get_settings", lambda: settings)
    monkeypatch.setattr(
        "src.api.dependencies.get_identity_provider",
        lambda: _FakeIdentityProvider(Permission.ADMIN),
    )

    dep = authorize(Permission.READ)

    with pytest.raises(AuthorizationException):
        await dep(authorization="InvalidHeader", x_api_key="", x_actor_id="system")

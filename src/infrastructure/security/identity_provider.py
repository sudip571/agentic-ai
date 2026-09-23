from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.application.interfaces.auth import Permission
from src.shared.configuration import Settings
from src.shared.errors import AuthorizationException, ExternalServiceException


@dataclass(frozen=True)
class IdentityContext:
    subject: str
    permission: Permission


class OIDCIntrospectionIdentityProvider:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def authenticate(self, bearer_token: str) -> IdentityContext:
        if not self._settings.auth_introspection_url:
            raise AuthorizationException("OIDC introspection URL is not configured")

        data = await self._introspect_token(bearer_token)

        if not bool(data.get("active", False)):
            raise AuthorizationException("Inactive token")

        subject = str(data.get("sub") or "")
        if not subject:
            raise AuthorizationException("Token subject is missing")

        permission = self._permission_from_claims(data)
        return IdentityContext(subject=subject, permission=permission)

    async def _introspect_token(self, bearer_token: str) -> dict[str, Any]:
        introspection_url = self._settings.auth_introspection_url
        if not introspection_url:
            raise AuthorizationException("OIDC introspection URL is not configured")

        payload = {"token": bearer_token}
        auth_tuple: tuple[str, str] | None = None
        if (
            self._settings.auth_introspection_client_id
            and self._settings.auth_introspection_client_secret
        ):
            auth_tuple = (
                self._settings.auth_introspection_client_id,
                self._settings.auth_introspection_client_secret,
            )

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.auth_introspection_timeout_seconds,
                transport=self._transport,
            ) as client:
                if auth_tuple is None:
                    response = await client.post(introspection_url, data=payload)
                else:
                    response = await client.post(
                        introspection_url,
                        data=payload,
                        auth=auth_tuple,
                    )
                response.raise_for_status()
                json_payload = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalServiceException("Identity provider timeout") from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceException("Identity provider request failed") from exc

        if not isinstance(json_payload, dict):
            raise AuthorizationException("Invalid identity response")
        return json_payload

    def _permission_from_claims(self, claims: dict[str, Any]) -> Permission:
        roles = self._read_roles(claims)
        role_map = {
            Permission.READ: self._settings.auth_read_role,
            Permission.WRITE: self._settings.auth_write_role,
            Permission.APPROVE: self._settings.auth_approve_role,
            Permission.ADMIN: self._settings.auth_admin_role,
        }

        if role_map[Permission.ADMIN] in roles:
            return Permission.ADMIN
        if role_map[Permission.APPROVE] in roles:
            return Permission.APPROVE
        if role_map[Permission.WRITE] in roles:
            return Permission.WRITE
        if role_map[Permission.READ] in roles:
            return Permission.READ

        raise AuthorizationException("Token does not have required billing role")

    def _read_roles(self, claims: dict[str, Any]) -> set[str]:
        roles: set[str] = set()

        role_claim = claims.get(self._settings.auth_role_claim)
        if isinstance(role_claim, list):
            roles.update(str(item) for item in role_claim)
        elif isinstance(role_claim, str):
            roles.add(role_claim)

        scope_claim = claims.get(self._settings.auth_scope_claim)
        if isinstance(scope_claim, str):
            roles.update(part for part in scope_claim.split(" ") if part)

        return roles

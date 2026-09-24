# Operations

## Local Startup

1. uv sync --extra dev
2. docker compose up -d postgres redis litellm
3. uv run alembic upgrade head
4. uv run python -m src.infrastructure.persistence.seed
5. uv run uvicorn src.api.main:app --reload

## Health

- GET /health/live
- GET /health/ready
- GET /metrics

## LiteLLM Dashboard

- URL: `http://localhost:4000/ui/login/`
- Bootstrap login uses `UI_USERNAME` and `UI_PASSWORD`.
- For production, create a dedicated proxy admin account and keep `disable_env_credential_login: true` in `litellm/config.yaml`.

## Enterprise Identity Mode

To enable enterprise auth:

1. Set AUTH_MODE=oidc_introspection
2. Configure AUTH_INTROSPECTION_URL
3. Configure AUTH_INTROSPECTION_CLIENT_ID
4. Configure AUTH_INTROSPECTION_CLIENT_SECRET
5. Configure role/scope mapping keys

## GitHub CI/CD Operations

Repository workflows:

1. `.github/workflows/ci.yml` for lint/type/test/build checks.
2. `.github/workflows/cd.yml` for image publish and production deploy.

Deployment model:

1. Build and publish immutable GHCR image tags.
2. Production deploy runs from protected GitHub Environment.
3. Runner federates to Azure via OIDC.
4. Runtime secrets are pulled from Azure Key Vault.
5. Docker Compose updates API and MCP services.
6. Alembic migration runs before health verification.

## Production Deployment Checklist

1. Ensure production environment approvals are active in GitHub.
2. Ensure self-hosted runner with billing-prod label is online.
3. Ensure Key Vault secrets are present.
4. Trigger CD workflow from main/tag/manual dispatch.
5. Verify /health/ready and /metrics after deployment.

## Rollback

1. Re-run CD for previous commit SHA image tag.
2. Re-run migration only if backward-compatible downgrade is planned.
3. Validate API and MCP health.
4. Confirm error rate and metrics normalization.

## Recovery Notes

- Duplicate credit prevention uses idempotency keys.
- Approval states are persisted and can be retried safely.

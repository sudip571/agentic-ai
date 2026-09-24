# GitHub Deployment Guide

## Recommended Delivery Model

This project uses GitHub Actions + GitHub Environments + OIDC federation to Azure + Azure Key Vault.

Why this is the default recommendation:

- Native GitHub ecosystem integration with low operational overhead.
- No long-lived cloud credentials in repository secrets.
- Deployment gates are enforced through GitHub Environments.
- Works with self-hosted runners for private network deployment targets.

## Pipeline Topology

1. CI workflow validates quality on pull request and main branch.
2. CD workflow builds and pushes immutable image tags to GHCR.
3. Production job requires environment approval and runs on self-hosted runner.
4. Runner federates identity to Azure using OIDC.
5. Secrets are read from Azure Key Vault at deployment time.
6. Docker Compose updates API, MCP, LiteLLM, and Redis services.
7. Migration step runs alembic upgrade head.
8. Health checks verify rollout.

## Prerequisites

1. A GitHub repository with Actions enabled.
2. A production self-hosted runner labeled:
   - self-hosted
   - linux
   - x64
   - billing-prod
3. Azure Entra workload identity federation configured for the GitHub repository environment.
4. Azure Key Vault with deployment secrets.

## GitHub Environment Setup

Create a production environment and require reviewer approval.

Environment variables:

- AZURE_KEY_VAULT_NAME
- AUTH_INTROSPECTION_URL
- AUTH_INTROSPECTION_CLIENT_ID
- AUTH_ROLE_CLAIM
- AUTH_SCOPE_CLAIM
- AUTH_READ_ROLE
- AUTH_WRITE_ROLE
- AUTH_APPROVE_ROLE
- AUTH_ADMIN_ROLE
- LLM_MODEL
- OLLAMA_API_BASE
- UI_USERNAME
- MCP_CLIENT_MODE
- MCP_SERVER_URL

Environment secrets:

- AZURE_CLIENT_ID
- AZURE_TENANT_ID
- AZURE_SUBSCRIPTION_ID

## Required Key Vault Secrets

- billing-database-url
- billing-mcp-service-token
- billing-introspection-client-secret
- billing-litellm-database-url
- billing-litellm-master-key
- billing-litellm-api-key
- billing-openai-api-key
- billing-anthropic-api-key
- billing-litellm-ui-password

## Triggering Deployment

1. Merge to main for continuous delivery.
2. Push a version tag (vX.Y.Z) for release deployment.
3. Or run workflow_dispatch manually from Actions.

## Rollback Procedure

1. Re-run CD workflow using a prior commit SHA.
2. Set BILLING_IMAGE to previous sha tag when re-deploying.
3. Validate:
   - /health/ready
   - /metrics
4. Review logs and workflow output before closing incident.

## Why Not Octopus By Default

Octopus is strong for multi-platform enterprise release orchestration. For this repository, GitHub-native Actions + Environments + OIDC already cover the required governance, secret handling, approvals, and runner strategy with less toolchain complexity.

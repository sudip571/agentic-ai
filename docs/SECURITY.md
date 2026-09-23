# Security

## Implemented Controls

- Input validation on API schemas.
- Dual-mode authorization:
	- API key mode for local development
	- OIDC introspection mode for enterprise identity
- Deterministic rule enforcement outside LLM.
- Idempotency control for credit creation.
- No secrets stored in code paths intended for production.
- External dependency failures are mapped to safe 503 responses.
- Request rate limiting and request-size limits.
- Security response headers and trace correlation ids.
- Secrets retrieval pattern through Azure Key Vault in CD workflow.

## Required Before Full Production Sign-Off

1. Add PII redaction policy for logs.
2. Add explicit security test suite for advanced prompt/tool injection scenarios.
3. Add periodic key rotation policy and automated validation in security pipeline.

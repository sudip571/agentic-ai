# ADR-003 LLM Provider Abstraction

## Context

The application must support model/runtime variation (local Ollama and future provider options) without scattering provider-specific logic across business code.

## Decision

Use LiteLLM as the gateway abstraction and keep provider/runtime details in infrastructure configuration.

## Alternatives

- Direct SDK calls in application code for each provider.
- Custom gateway built in-house.

## Consequences

- Cleaner separation of concerns.
- Easier provider/model switching through configuration.
- Additional dependency and operational layer to manage.

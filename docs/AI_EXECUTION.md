# AI Execution

## LLM Responsibilities

- Interpret complaint text.
- Extract monetary values.
- Provide structured response payload.

## Safety Boundaries

- Prompt text does not grant authority.
- Output is schema-validated.
- LLM cannot invoke side effects directly.
- Domain rules determine whether correction is allowed.

## Failure Handling

- LLM timeout/failure falls back to regex extraction.
- If extraction is insufficient, deterministic validations stop unsafe flow.

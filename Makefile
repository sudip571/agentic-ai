install:
	uv sync --extra dev

lint:
	uv run ruff check .

typecheck:
	uv run mypy src

test:
	uv run pytest -q

run-api:
	uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000

seed:
	uv run python -m src.infrastructure.persistence.seed

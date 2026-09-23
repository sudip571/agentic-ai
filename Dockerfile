FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
COPY mcp_server ./mcp_server
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY docs ./docs
COPY litellm ./litellm

RUN uv pip install --system .

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

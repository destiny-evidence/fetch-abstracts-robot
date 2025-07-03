FROM python:3.13-slim-bookworm AS base
WORKDIR /app

FROM base AS builder

RUN pip install poetry poetry-plugin-bundle
COPY pyproject.toml poetry.lock README.md ./

RUN poetry bundle venv -vvv --only=main /app/.venv;

FROM base AS final
COPY --from=builder /app/.venv /app/.venv

COPY app/ ./app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001
ENTRYPOINT ["fastapi",  "run", "app/main.py", "--port", "8001"]

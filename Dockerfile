FROM python:3.13-slim-bookworm AS base

WORKDIR /app

FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run uv installer and remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --locked

FROM base AS final

COPY src/app/ ./app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001
ENTRYPOINT ["uv", "run", "fastapi",  "run", "src/app/main.py", "--port", "8001"]

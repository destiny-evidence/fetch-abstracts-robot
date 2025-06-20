FROM python:3.13-slim-bookworm AS base
WORKDIR /app

FROM base AS builder

RUN apt-get -qy update && apt-get install --no-install-recommends -y openssh-client

RUN pip install poetry poetry-plugin-bundle
COPY pyproject.toml poetry.lock README.md ./

RUN mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
RUN --mount=type=ssh poetry bundle venv -vvv --only=main /app/.venv;

FROM base AS final
COPY --from=builder /app/.venv /app/.venv

COPY app/ ./app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001
ENTRYPOINT ["fastapi",  "run", "app/main.py", "--port", "8001"]

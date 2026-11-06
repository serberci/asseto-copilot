FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY packages packages
COPY apps/backend apps/backend
COPY apps/windows-agent apps/windows-agent
RUN uv sync --frozen --package coach-backend --no-dev
ENV COACH_DATA_DIR=/data
EXPOSE 8080
CMD ["uv", "run", "--frozen", "--no-dev", "--package", "coach-backend", "coach-backend"]

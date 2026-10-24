# One image: the FastAPI service by default, the CLI for batch jobs (`docker run IMAGE certivity bench`).
# Configuration comes from environment variables; secrets from the host's secret store. Run data
# lives on a mounted volume at /app/data. The challenge package is mounted or copied at build time.
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY server ./server
COPY industrial-ai-hackathon ./industrial-ai-hackathon
COPY --from=web /web/dist ./web/dist
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" CERTIVITY_DATA_DIR=/app/data
VOLUME ["/app/data"]
EXPOSE 8000
CMD ["certivity", "serve", "--host", "0.0.0.0", "--port", "8000"]

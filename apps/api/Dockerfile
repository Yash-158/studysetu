FROM python:3.12-slim
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*
COPY apps/api/pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml
COPY apps/api/app ./app
COPY config ./config
COPY prompts ./prompts
COPY scripts ./scripts
COPY db ./db
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Build context is the repo root (see infra/docker-compose.yml + .github/workflows/deploy.yml).

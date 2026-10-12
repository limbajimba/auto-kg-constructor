FROM python:3.13-slim

# No system deps needed — Gemini is an API, not a local model

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Copy proof code
COPY proof/ proof/

# Runtime directories (corpora mounted as volume)
RUN mkdir -p corpora proof/outputs

# Default: run the parse
CMD ["uv", "run", "python", "-m", "proof.01_parse"]

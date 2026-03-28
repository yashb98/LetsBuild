# LetsBuild — Production Multi-Stage Dockerfile

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml ./
COPY README.md ./

# Create a minimal package structure so pip can resolve the package
RUN mkdir -p letsbuild && touch letsbuild/__init__.py

# Install production dependencies into a prefix directory
RUN pip install --no-cache-dir --prefix=/install ".[web]"

# ── Stage 2: Production ──────────────────────────────────────────────────────
FROM python:3.12-slim AS production

LABEL org.opencontainers.image.title="LetsBuild" \
      org.opencontainers.image.description="Autonomous Portfolio Factory" \
      org.opencontainers.image.source="https://github.com/yashb98/LetsBuild" \
      org.opencontainers.image.version="3.0.0-alpha" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY letsbuild/ ./letsbuild/
COPY skills/ ./skills/
COPY pyproject.toml ./
COPY README.md ./

# Re-install the package itself (editable install not possible in production)
RUN pip install --no-cache-dir --no-deps .

# Create non-root user
RUN groupadd -r letsbuild && useradd -r -g letsbuild -d /app -s /sbin/nologin letsbuild

# Create data directories with correct ownership
RUN mkdir -p /app/data /app/logs && chown -R letsbuild:letsbuild /app/data /app/logs

USER letsbuild

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["python", "-m", "uvicorn", "letsbuild.gateway.api:app", "--host", "0.0.0.0", "--port", "8000"]

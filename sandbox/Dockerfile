FROM ubuntu:24.04

LABEL maintainer="yashb98" \
      description="LetsBuild sandbox environment for code generation and validation" \
      org.opencontainers.image.title="LetsBuild Sandbox" \
      org.opencontainers.image.source="https://github.com/yashb98/LetsBuild"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System packages — install as root before switching to sandbox user
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev python3-pip \
    nodejs npm \
    golang-go \
    curl git wget ca-certificates \
    build-essential pkg-config \
    postgresql-client redis-tools \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Rust (minimal install as root, available system-wide)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain stable --profile minimal --no-modify-path
ENV PATH="/root/.cargo/bin:${PATH}"

# Node.js LTS (v20) via n
RUN npm install -g n && n 20 && npm install -g pnpm yarn typescript

# Python tools (installed globally before switching user)
RUN pip install --break-system-packages --no-cache-dir \
    ruff mypy pytest pytest-asyncio pytest-cov \
    black isort pylint \
    poetry pipenv \
    httpx pydantic anthropic

# Create non-root sandbox user
RUN useradd -ms /bin/bash sandbox

# Create mount point directories as root with correct permissions
RUN mkdir -p /mnt/workspace /mnt/skills /mnt/outputs \
    && chown sandbox:sandbox /mnt/workspace /mnt/outputs \
    && chmod 755 /mnt/skills  # read-only at runtime via Docker bind mount

# Mount points:
#   /mnt/workspace  — generated project files (read/write)
#   /mnt/skills     — skill files from host (bind mount as read-only)
#   /mnt/outputs    — validation results and build artifacts
VOLUME ["/mnt/workspace", "/mnt/outputs"]

USER sandbox
WORKDIR /mnt/workspace

# Expose Rust cargo in sandbox user PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Health check — verify core runtimes are functional
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3.12 --version && node --version && go version

CMD ["/bin/bash"]

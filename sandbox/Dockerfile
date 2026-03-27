FROM ubuntu:24.04

LABEL maintainer="yashb98" \
      description="LetsBuild sandbox environment for code generation and validation"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip \
    nodejs npm \
    golang-go \
    curl git wget ca-certificates \
    build-essential pkg-config \
    postgresql-client redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Rust (minimal)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

# Node.js LTS via n
RUN npm install -g n && n 20 && npm install -g pnpm yarn

# Python tools
RUN pip install --break-system-packages --no-cache-dir \
    ruff mypy pytest pytest-asyncio pytest-cov \
    black isort pylint \
    poetry pipenv

# Non-root user
RUN useradd -ms /bin/bash sandbox
USER sandbox
WORKDIR /mnt/workspace

# Directories
RUN mkdir -p /mnt/workspace /mnt/outputs
VOLUME ["/mnt/workspace", "/mnt/outputs"]

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3.12 --version && node --version

CMD ["/bin/bash"]

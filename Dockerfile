# ==============================================================================
# LocalOps AI — Production GPU Container
# Target Hardware: NVIDIA RTX 3070 Laptop (8 GB VRAM) / CUDA 12.4
# Multi-Stage Build:
#   Stage 1: Frontend Dashboard Builder (Node.js 20)
#   Stage 2: Python CUDA Wheels Builder
#   Stage 3: Minimal Non-Root Production Runtime
# ==============================================================================

# Stage 1: Build Frontend Dashboard Static Assets
FROM node:20-alpine AS frontend-builder

WORKDIR /dashboard

COPY dashboard/package*.json ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build

# Stage 2: Build Dependencies
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .

# Install PyTorch with matching CUDA 12.4 runtime wheels, followed by application dependencies
RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 && \
    pip3 install --no-cache-dir -r requirements.txt

# Stage 3: Minimal Non-Root Production Runtime
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runner

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/cache/huggingface \
    TRANSFORMERS_CACHE=/app/cache/huggingface \
    PORT=8000 \
    LOCALOPS_CONFIG_PATH=/app/configs/api.yaml

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python site-packages from builder
COPY --from=builder /usr/local/lib/python3.10/dist-packages /usr/local/lib/python3.10/dist-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create unprivileged application user
RUN groupadd -g 10001 localops && \
    useradd -u 10001 -g localops -s /bin/bash -m localops

WORKDIR /app

# Copy application source, configuration, runbooks, and locked artifacts
COPY configs/ /app/configs/
COPY src/ /app/src/
COPY runbooks/ /app/runbooks/
COPY artifacts/ /app/artifacts/

# Copy compiled dashboard static assets from frontend-builder
COPY --from=frontend-builder /dashboard/dist /app/dashboard/dist

# Prepare persistent mount directories with correct ownership
RUN mkdir -p /app/cache/huggingface /app/logs && \
    chown -R localops:localops /app

USER localops:localops

EXPOSE 8000

# Docker native liveness healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["python3", "-m", "uvicorn", "src.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

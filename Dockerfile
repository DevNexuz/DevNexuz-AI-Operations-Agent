# syntax=docker/dockerfile:1.6
# =============================================================================
# AI Operations Agent — Dockerfile
# =============================================================================
# Multi-stage build:
#   - "builder" stage: installs deps into a virtualenv (uses pip cache mount).
#   - "runtime" stage: only the venv + app code, runs as non-root.
#
# Image size target: < 600 MB.
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: builder
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps that some Python wheels may need (matplotlib, pandas, etc.).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Create venv in a known location so we can copy it to the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python deps using pip's BuildKit cache (much faster on rebuilds).
WORKDIR /tmp/build
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
 && pip install -r requirements.txt


# -----------------------------------------------------------------------------
# Stage 2: runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Force matplotlib to a writable cache dir owned by the non-root user.
    MPLCONFIGDIR=/home/agent/.cache/matplotlib

# Minimal runtime libs needed by matplotlib/pandas (libgomp for numpy).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user. Containers should never run as root.
RUN groupadd --system --gid 1000 agent \
 && useradd  --system --uid 1000 --gid agent --create-home --shell /bin/bash agent

# Bring in the prebuilt virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy app code with correct ownership.
COPY --chown=agent:agent . .

# Make sure the dirs the agent writes to are owned by the non-root user.
RUN mkdir -p outputs data \
 && chown -R agent:agent /app /home/agent

USER agent

# Default command runs the demo so `docker run <image>` just works out of the box.
ENTRYPOINT ["python", "main.py"]
CMD ["--demo"]

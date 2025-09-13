# syntax=docker/dockerfile:1.7
# ───────────────────────────── builder ─────────────────────────────
FROM public.ecr.aws/docker/library/python:3.12-slim AS builder

ARG APP_HOME=/app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=on

# Build deps for wheels (no runtime bloat)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_HOME}

# Copy ONLY requirement files first for better layer caching
COPY requirements.txt /tmp/reqs/root.txt
COPY lib/erp_base/requirements.txt /tmp/reqs/erp_base.txt
COPY lib/cas_auth/requirements.txt /tmp/reqs/cas_auth.txt

# Build all wheels in one go (stable & cache-friendly)
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps \
      -r /tmp/reqs/root.txt \
      -r /tmp/reqs/erp_base.txt \
      -r /tmp/reqs/cas_auth.txt \
      -w /wheels

# ───────────────────────────── runtime ─────────────────────────────
FROM public.ecr.aws/docker/library/python:3.12-slim AS runtime

ARG APP_HOME=/app
ENV APP_HOME=${APP_HOME}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on

# Minimal runtime deps (no compilers). libgl1 for OpenCV if used.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 bash tini curl ca-certificates libgl1 \
 && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd -ms /bin/bash appuser

WORKDIR ${APP_HOME}

# Install prebuilt wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*

# Copy application code last (so code changes don't bust deps layers)
COPY --chown=appuser:appuser . ${APP_HOME}

# Make sure scripts are executable in the image (bind mount may override at runtime; we also re-ensure in entrypoint)
RUN chmod +x docker/*.sh || true

# Drop privileges
USER appuser

# Tiny init so signals are handled and zombies are reaped
ENTRYPOINT ["tini", "--", "bash", "docker/entrypoint.sh"]

# Default CMD is overridden by docker-compose per service
CMD ["bash", "-lc", "echo 'Set command in compose (web/worker/beat)' && sleep infinity"]

# ============================================================
# ProjectMind AI — Production Dockerfile
# Multi-stage, lean, secure containerization
# ============================================================

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and force unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install essential system dependencies (curl for container healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group
RUN groupadd -g 1000 projectmind && \
    useradd -u 1000 -g projectmind -s /bin/bash -m projectmind

# Install Python dependencies in separate layer for optimal caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code with non-root ownership
COPY --chown=projectmind:projectmind backend/ ./backend/
COPY --chown=projectmind:projectmind projectmind/ ./projectmind/
COPY --chown=projectmind:projectmind scripts/ ./scripts/

# Ensure non-root user owns the app directory
RUN chown -R projectmind:projectmind ${APP_HOME}

# Switch to non-root user
USER projectmind

# Expose HTTP service port
EXPOSE 8000

# Container healthcheck querying FastAPI root endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Launch ASGI server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]


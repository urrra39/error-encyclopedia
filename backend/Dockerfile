# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Error Encyclopedia — backend (FastAPI) image
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# Keep Python lean and predictable inside containers:
#   - PYTHONUNBUFFERED       -> logs stream straight to the container output.
#   - PYTHONDONTWRITEBYTECODE-> no .pyc clutter in the image layers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so this layer is cached across source changes.
# asyncpg, psycopg2-binary, and pydantic-core all publish manylinux wheels for
# CPython 3.11, so the slim image needs no compiler toolchain.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the application source.
COPY . .

# Drop root privileges for the running process.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Bind to 0.0.0.0 so the service is reachable from outside the container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

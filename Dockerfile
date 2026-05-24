# Minimal production image for the FreshList backend.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so the layer is cached across code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application package.
COPY app ./app

EXPOSE 8000

# Bind to all interfaces inside the container; the orchestrator maps the port.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

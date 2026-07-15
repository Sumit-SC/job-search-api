# Koyeb-ready container.
# NOTE: This uses the Playwright base image (includes Chromium) so headless can be enabled later.
# If you want a smaller image (RSS/API only), we can switch to python:3.11-slim.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY local-ui /app/local-ui

# Setup writable permissions for Hugging Face Spaces non-root user (UID 1000)
RUN mkdir -p /app/data && chmod -R 777 /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV ENABLE_HEADLESS=0
ENV USE_JOBSPY=0
ENV SCRAPER_CONCURRENCY=3
ENV JOBS_SCRAPER_DATA_DIR=/app/data

# Railway, Render, Cloud Run set PORT at runtime. Default 8000 for local Docker.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

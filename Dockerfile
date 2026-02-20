# Playwright image includes Chromium for headless scrapers (LinkedIn, Indeed, Naukri).
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY local-ui /app/local-ui

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Railway, Render, Cloud Run set PORT at runtime. Default 8000 for local Docker.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

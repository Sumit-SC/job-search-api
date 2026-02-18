FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

ENV PYTHONUNBUFFERED=1

# Railway sets $PORT. Default to 8000 for local runs.
CMD ["bash", "-lc", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

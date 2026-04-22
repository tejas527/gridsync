# ── GridSync Scheduler Image ──────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# PyYAML is now required to read regions.yaml
RUN pip install --no-cache-dir pyyaml

# Copy application files
COPY scheduler.py .
COPY regions.yaml .

CMD ["python", "scheduler.py"]

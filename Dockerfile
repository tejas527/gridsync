# ── GridSync Scheduler Image ──────────────────────────────────────────────────
# The k3s binary is mounted from the host at runtime via docker-compose volumes,
# so there is no need to install kubectl or any extra tooling here.
FROM python:3.11-slim

WORKDIR /app

# PyYAML is required to read regions.yaml
RUN pip install --no-cache-dir pyyaml

# Copy application files
COPY scheduler.py .
COPY regions.yaml .

CMD ["python", "scheduler.py"]

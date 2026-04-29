FROM python:3.11-slim

# Install kubectl (Standard tool for K8s interaction)
RUN apt-get update && apt-get install -y curl && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && mv kubectl /usr/local/bin/

WORKDIR /app

RUN pip install --no-cache-dir pyyaml

COPY scheduler.py .
COPY regions.yaml .

# Ensure the app can run without root-only permissions if needed
CMD ["python", "scheduler.py"]

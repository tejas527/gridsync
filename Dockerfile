# Use a slim Python base — keeps the image small
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy scheduler into the image
COPY scheduler.py .

# No pip installs needed — scheduler only uses stdlib (subprocess, random, time)

# Default command runs the scheduler
CMD ["python", "scheduler.py"]

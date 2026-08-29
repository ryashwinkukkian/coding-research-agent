FROM python:3.11-slim

# git isn't in the slim base image, but this tool depends on it
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .
COPY tools/ ./tools/

ENTRYPOINT ["python", "agent.py"]
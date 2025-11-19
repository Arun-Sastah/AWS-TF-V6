FROM python:3.12-slim

# Set working directory
WORKDIR /worker

# -----------------------------
# Install system tools + terraform
# -----------------------------
RUN apt-get update && apt-get install -y wget unzip \
    && wget https://releases.hashicorp.com/terraform/1.9.5/terraform_1.9.5_linux_amd64.zip \
    && unzip terraform_1.9.5_linux_amd64.zip -d /usr/local/bin/ \
    && rm terraform_1.9.5_linux_amd64.zip

# -----------------------------
# Python dependencies
# -----------------------------
COPY worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------
# Copy worker code
# -----------------------------
COPY worker/ ./worker

# -----------------------------
# Copy backend code (for imports + templates)
# -----------------------------
COPY backend/app ./app
COPY backend/modules ./modules

# -----------------------------
# Fix Windows CRLF issues (safe method)
# -----------------------------
RUN apt-get update && apt-get install -y dos2unix && \
    find . -type f -name "*.py" -exec dos2unix {} \; && \
    apt-get purge -y dos2unix && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Start worker
# -----------------------------
CMD ["python", "worker/worker.py"]

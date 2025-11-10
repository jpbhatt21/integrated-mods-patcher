# Multi-stage Dockerfile for Python Flask app (builder -> runtime)
# Builder stage: installs build deps and builds wheels for requirements
# Runtime stage: installs wheels only and contains runtime extraction tools

# Builder
FROM python:3.11-slim AS builder

WORKDIR /src
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build tools required by some Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libssl-dev \
        libffi-dev \
        liblzma-dev \
        libbz2-dev \
        zlib1g-dev \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels
COPY requirements.txt ./
RUN pip install --upgrade pip wheel setuptools \
    && mkdir /wheels \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install minimal runtime packages including extraction tools used by the app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        unzip \
        p7zip-full \
        unrar-free \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install them
COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && pip cache purge

# Copy application source
COPY . .

# Create directories used by the app
RUN mkdir -p download_temp extract_temp templates

EXPOSE 5000

# Use waitress to serve the Flask app (expects `app:app` in repo root)
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "app:app"]

# Builder: build frontend assets
FROM node:24-slim AS builder
WORKDIR /app/frontend

# copy package files first for cached installs
COPY frontend/package*.json ./
RUN npm ci --silent --no-audit || npm install --silent

# copy the rest of frontend and build
COPY frontend/ ./
RUN npm run build

# Runtime: minimal Python image
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# install runtime system deps
# enable non-free repository (required for packages like p7zip-rar) and install deps
# Be robust when /etc/apt/sources.list is missing (some minimal images use sources.list.d)
RUN set -eux; \
    # If the “debian.sources” format is used:
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/^Components: \(.*\)$/Components: \1 contrib non-free non-free-firmware/' /etc/apt/sources.list.d/debian.sources; \
    else \
      # fallback to modifying sources.list if it exists
      sed -i 's#/deb http://#deb http://#g; s/main/main contrib non-free non-free-firmware/' /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
       build-essential \
       libssl-dev \
       p7zip-full \
       p7zip-rar \
       unrar-free \
       unzip; \
    apt-get clean; rm -rf /var/lib/apt/lists/*

# copy Python deps descriptor then install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy backend code and the built frontend from builder
COPY backend/ ./backend
COPY --from=builder /app/frontend/dist ./backend/dist

EXPOSE 5000
CMD ["python3", "backend/app.py"]
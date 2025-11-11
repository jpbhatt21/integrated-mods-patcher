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
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    p7zip-full unzip unrar-free \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# copy Python deps descriptor then install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy backend code and the built frontend from builder
COPY backend/ ./backend
COPY --from=builder /app/frontend/dist ./backend/dist

EXPOSE 5000
CMD ["python3", "backend/app.py"]
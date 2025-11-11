FROM nikolaik/python-nodejs:python3.13-nodejs24-slim
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    p7zip-full unzip unrar-free \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/frontend
RUN npm install && npm run build

WORKDIR /app
RUN mkdir -p backend/dist \
    && cp -r frontend/dist/* backend/dist/ || true

EXPOSE 5000
CMD ["bash", "-c", "python3 backend/app.py"]
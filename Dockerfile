FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

COPY ./entrypoint_backend.sh /entrypoint_backend.sh
COPY ./entrypoint_worker.sh /entrypoint_worker.sh

RUN chmod +x /entrypoint_backend.sh /entrypoint_worker.sh

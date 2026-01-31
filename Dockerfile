FROM python:3.10-slim

WORKDIR /app

# Установка системных зависимостей для сборки psycopg2
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаем папку для сессий внутри контейнера
RUN mkdir -p /app/sessions

COPY . .
ENV PYTHONPATH=/app
FROM python:3.13-slim

WORKDIR /app

# Установка системных зависимостей (при необходимости)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt ./

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной исходный код проекта
COPY . .

# Убеждаемся, что скрипт запуска доступен
RUN chmod +x run_agent.py

# Точка входа по умолчанию (аргументы прокинет проверяющий скрипт)
ENTRYPOINT ["python3"]

FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
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

# Убеждаемся, что скрипты доступны для исполнения
RUN chmod +x run_agent.py main.py

# Устанавливаем точку входа через sh, чтобы отрабатывали оба шага подряд,
# а "$@" подставит аргументы командной строки (например, --tasks-dir /data/tasks)
ENTRYPOINT ["sh", "-c", "python3 /app/main.py /data/tasks /app/config.yaml && python3 /app/run_agent.py \"$@\"", "--"]

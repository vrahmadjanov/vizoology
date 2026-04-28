FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
# - libpq-dev, python3-dev, gcc, libpq5 - зависимости для psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Удаление build зависимостей
RUN apt-get purge -y gcc libpq-dev && apt-get autoremove -y

# Копирование приложения
COPY . .

# Создание директорий
RUN mkdir -p /app/staticfiles /app/media

# Expose порт
EXPOSE 8000

# Запуск приложения по умолчанию
CMD ["/bin/sh", "-c", "python manage.py run"]
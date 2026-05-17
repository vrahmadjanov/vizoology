# Vizoology — Django + Gunicorn, статика через WhiteNoise при USE_WHITENOISE=true.
# Сборка: docker build -t vizoology .
# Запуск требует переменных окружения (SECRET_KEY, ALLOWED_HOSTS, USE_WHITENOISE=true, БД и т.д.), см. .env.example.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=vizoology.settings

WORKDIR /app

# libpq5 — runtime psycopg2; libpq-dev + build-essential — сборка psycopg2 (нужен pg_config).
# libgomp1 — torch/numpy/scipy в slim. После pip сборочные пакеты удаляются.
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libpq5 \
        libgomp1 \
    && pip install -r requirements.txt \
    && apt-get purge -y build-essential libpq-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/media \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Нужны переменные из env (SECRET_KEY, ALLOWED_HOSTS, USE_WHITENOISE=true для статики, БД и т.д.)
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate --noinput && exec python manage.py run --bind ${GUNICORN_BIND:-0.0.0.0:8000}"]

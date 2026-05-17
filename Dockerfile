# Vizoology — Django + Gunicorn, статика через WhiteNoise при USE_WHITENOISE=true.
# Сборка: docker build -t vizoology .
# Запуск требует переменных окружения (SECRET_KEY, ALLOWED_HOSTS, USE_WHITENOISE=true, БД и т.д.), см. .env.example.

# --- сборка зависимостей (компилятор и libpq-dev не попадают в финальный образ) ---
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements.txt .
# Torch с индекса CPU — обычно на порядок меньше колеса с CUDA с PyPI
RUN pip install --no-cache-dir \
        "torch==2.11.0" \
        --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple \
    && pip install --no-cache-dir -r requirements.txt \
    && find /venv -depth -type d -name __pycache__ -exec rm -rf {} \; 2>/dev/null || true \
    && find /venv -type f -name "*.pyc" -delete 2>/dev/null || true

# --- runtime: только системные библиотеки и venv ---
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=vizoology.settings \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/media

COPY --from=builder /venv /venv

COPY . .

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate --noinput && exec python manage.py run --bind ${GUNICORN_BIND:-0.0.0.0:8000}"]

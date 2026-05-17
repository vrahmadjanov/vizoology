## Vizoology

Проект для поиска ответов по документации Visiology из Confluence. Реализован полный RAG-контур: страницы Confluence скачиваются в БД, текст делится на чанки, для чанков генерируются **локальные** embeddings и сохраняются в PostgreSQL с расширением **pgvector**; по запросу находятся ближайшие фрагменты, после чего (при достаточной релевантности) **DeepSeek** через OpenAI-совместимый API формирует краткий структурированный ответ по найденному контексту.

Пример релевантной выдачи поиска:

![Релевантные результаты поиска по документации](image.png)

### Архитектура и стек

- **Django** 6.x, WSGI-приложение `vizoology.wsgi`.
- **Приложения**: `shared` (общие утилиты, миграции для pgvector), `confluence` (синхронизация, чанки, векторный поиск), `ai` (RAG, клиент DeepSeek, история ответов), `parser` (чтение/запись Excel и команда пакетного опроса RAG).
- **База данных**: PostgreSQL с **pgvector** — векторные поля и индексы используются миграциями `confluence`. Режим `DATABASE_ENGINE=sqlite` в настройках предусмотрен для разработки без Postgres, но **индексация и поиск по embeddings с SQLite не работают**; для описанного ниже пайплайна нужен Postgres.
- **Эмбеддинги**: локально, через `sentence-transformers`, по умолчанию модель `intfloat/multilingual-e5-small` (размерность вектора 384, должна совпадать с `EMBEDDING_DIMENSIONS` в `.env`).
- **Генерация ответа**: DeepSeek (`DEEPSEEK_API_KEY`), модель по умолчанию задаётся в `DEEPSEEK_MODEL_NAME`, база API — в `DEEPSEEK_API_BASE` (см. `.env.example`).

Переменные для Confluence в `settings.py` также читаются под совместимыми именами: `CONFLUENCE_URL`, `ATLASSIAN_BASE_URL`, `ATLASSIAN_SPACE_KEY`, `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN` и др. — см. `vizoology/settings.py`, блок Confluence.

### Что уже умеет

- Подключаться к Confluence через Atlassian API (`atlassian-python-api`).
- Синхронизировать пространства документации, например `3v16` и ViHelp (`trouble`).
- Извлекать plain text из страниц.
- Делить текст на логические чанки.
- Генерировать embeddings локальной моделью и искать ближайшие чанки в **pgvector** (cosine distance, HNSW-индекс).
- Строить ответ на вопрос через RAG с проверкой порога релевантности `RAG_MIN_SCORE` и сохранять сессии в модель `ai.QuestionAnswerHistory` (доступ в Django Admin).
- Обрабатывать **пакет вопросов из Excel** (`.xlsx`): для каждой непустой ячейки в колонке вопросов вызывается тот же RAG, что и у команды `ask`; результаты записываются **в тот же файл** в три соседние колонки (краткий ответ, источники, обоснование). Подробнее — в разделе **Пакетная обработка Excel** ниже.

### Быстрый старт

1. Создать виртуальное окружение и установить зависимости:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

2. Скопировать `.env.example` в `.env` и заполнить как минимум:

   - `SECRET_KEY` — обязателен для Django.
   - Доступы к Confluence (см. пример ниже).
   - Для **полного RAG** (команды `ask` и `ask_excel`): `DEEPSEEK_API_KEY`.
   - Для работы с БД из этого репозитория через Docker: после `docker compose up -d db` контейнер пробрасывает Postgres на **порт хоста `65432`** (внутри контейнера остаётся `5432`). В `.env` укажите, например:

```env
DATABASE_ENGINE=postgresql
DATABASE_HOST=localhost
DATABASE_PORT=65432
DATABASE_NAME=vizoology
DATABASE_USER=vizoology_user
DATABASE_PASSWORD=vizoology_password
```

Образ и учётные данные по умолчанию совпадают с `docker-compose.yml`.

Минимальный набор для Confluence:

```env
CONFLUENCE_BASE_URL=https://your-site.atlassian.net/wiki
CONFLUENCE_SPACE_KEY=3v16
CONFLUENCE_USERNAME=you@example.com
CONFLUENCE_API_TOKEN=your-token
```

3. Запустить Postgres с pgvector:

```bash
docker compose up -d db
```

4. Применить миграции:

```bash
.venv/bin/python manage.py migrate
```

### Индексация документации

Для основного пространства из `.env` (`CONFLUENCE_SPACE_KEY`):

```bash
.venv/bin/python manage.py sync_pages
.venv/bin/python manage.py build_chunks
.venv/bin/python manage.py embed_chunks
```

Для ViHelp:

```bash
.venv/bin/python manage.py sync_pages --space-key trouble --batch-size 10 --retries 3
.venv/bin/python manage.py build_chunks --space-key trouble
.venv/bin/python manage.py embed_chunks
```

Команда `embed_chunks` обрабатывает все чанки в БД, которым нужна векторизация (в том числе после добавления нового пространства).

### Поиск и ответы (RAG)

**Только векторный поиск** по чанкам (без вызова LLM):

```bash
.venv/bin/python manage.py search "как работать с mongodb в cli" --top-k 5
```

Команда выводит ближайшие чанки, название страницы, ссылку на Confluence и score релевантности.

**Ответ на вопрос** по документации: поиск контекста + вызов LLM (DeepSeek) и сохранение записи в историю:

```bash
.venv/bin/python manage.py ask "как работать с mongodb в cli" --top-k 5
```

Порог релевантности по умолчанию задаётся `RAG_MIN_SCORE` в `.env`; при низком score модель не вызывается, пользователю возвращается сообщение о недостатке данных (при этом найденные фрагменты могут быть показаны в выводе команды).

История запросов доступна в админке: `/admin/` → модель **Question answer histories**.

### Пакетная обработка Excel

Команда **`ask_excel`** читает вопросы из колонки в файле **`.xlsx`**, для каждой строки с непустым текстом вопроса вызывает тот же пайплайн, что и `ask`, затем сохраняет книгу **по тому же пути** (файл перезаписывается).

**Соглашения по книге:**

- Отдельной строки заголовков нет — первая строка листа обрабатывается так же, как и остальные.
- Номера колонок задаются **буквами** Excel (`Q`, `AA`, …).
- Строки с **пустой** ячейкой в колонке вопросов пропускаются.

**Запись ответа:** три **подряд идущие** колонки — краткий ответ, текстовый блок источников (в духе вывода `ask`), обоснование (`reasoning_summary`). По умолчанию они начинаются **в первой колонке справа** от колонки вопросов (если вопросы в `Q`, результат — в `R`, `S`, `T`). Свою первую колонку можно задать флагом `--answers-start-col`.

**Переменные окружения** (см. `.env.example`): `PARSER_DEFAULT_QUESTION_COLUMN_LETTER` — буква колонки с вопросами по умолчанию, если в команде не передан `--questions-col`.

**Загрузка через браузер:** страница приложения **`presentation`**, URL **`/ask/`** — после отправки формы открывается **`/ask/jobs/<uuid>/`**: ответ «файл принят» приходит сразу, готовность и **ссылка на скачивание** `*_answered.xlsx` появляются по мере обработки (опрос статуса в браузере). Исходные и готовые файлы сохраняются в **`MEDIA_ROOT`** (по умолчанию каталог **`media/`** в корне проекта).

**Примеры:**

```bash
# Колонка вопросов из .env (по умолчанию Q), активный лист, ответы справа от вопроса
.venv/bin/python manage.py ask_excel ./questions.xlsx

# Явно указать колонку вопросов и лист
.venv/bin/python manage.py ask_excel ./questions.xlsx --questions-col D --sheet "Лист1"

# Блок ответа начинается с колонки G (занято G:H:I)
.venv/bin/python manage.py ask_excel ./questions.xlsx --questions-col D --answers-start-col G
```

Те же параметры контекста, что у `ask`: `--top-k`, `--min-score`. Флаг **`--no-history`** отключает запись в `QuestionAnswerHistory` для каждой строки. При ошибке RAG на строке в первую колонку блока ответа пишется текст ошибки, затем файл всё равно сохраняется после полного прохода.

Условия те же, что для одиночного `ask`: рабочий **Postgres + индекс** для поиска и **`DEEPSEEK_API_KEY`** там, где нужен вызов модели.

### Запуск веб-сервера (production)

В `vizoology/urls.py` подключены **админка** и HTTP-слой **`presentation`** (пакетный Excel, **`/ask/`**, задания **`/ask/jobs/<uuid>/`**). Для отдачи админки, страницы и статики в production можно использовать Gunicorn:

```bash
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py run --bind 0.0.0.0:8000
```

Параметры workers/threads и bind можно задать через аргументы команды или переменные окружения `GUNICORN_*` (см. `shared/management/commands/run.py`). В `docker-compose.yml` закомментирован пример сервиса приложения с `Dockerfile` — при необходимости его можно раскомментировать и донастроить.

`USE_WHITENOISE=true` в `.env` включает раздачу статики через WhiteNoise (см. `vizoology/settings.py`).

### Полезные проверки

```bash
.venv/bin/python manage.py healthcheck
.venv/bin/python manage.py healthcheck --embeddings --limit 1
.venv/bin/python manage.py test confluence ai parser presentation
```

### Зависимости

Основные библиотеки перечислены в `requirements.txt` (Django, psycopg2, pgvector, sentence-transformers, torch/transformers, **openai** (DeepSeek), **openpyxl**, gunicorn, whitenoise и др.). Первая векторизация скачает выбранную embedding-модель с Hugging Face — учитывайте объём диска и время загрузки.

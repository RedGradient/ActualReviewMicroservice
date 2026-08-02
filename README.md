# Review Parser Microservice

Микросервис для сбора и хранения отзывов организаций с картографических и отзовых площадок. Предоставляет REST API для запуска парсинга в фоне и получения сохранённых отзывов.

## Возможности

- Парсинг отзывов с **Yandex Maps**, **2GIS**, **VL.ru**
- Асинхронный запуск синхронизации через **Celery** (параллельно по провайдерам)
- REST API с документацией **Swagger**
- Django Admin для управления организациями, филиалами и отзывами
- Периодический парсинг всех филиалов (Celery Beat, каждое воскресенье в 06:00 MSK)

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Django 5.2, Django REST Framework |
| Очередь задач | Celery 5.3 |
| Брокер / кэш | Redis |
| БД | SQLite (по умолчанию) |
| Браузерная автоматизация | Playwright (Chromium) |
| Документация API | drf-yasg |

## Архитектура

```
POST /api/v1/sync/
        │
        ▼
  Celery chord
        ├── parse_single_provider (yandex)  ─┐
        ├── parse_single_provider (2gis)    ─┼── параллельно
        └── parse_single_provider (vlru)    ─┘
                        │
                        ▼
              merge_provider_results
                        │
                        ▼
                 SUCCESS + task_id
```

Клиент получает один `task_id` (id chord). Задача считается выполненной, когда отработали **все** парсеры и результат объединён.

## Быстрый старт (Docker)

```bash
docker compose up --build
```

Сервисы:

| Сервис | Порт | Описание |
|--------|------|----------|
| `web` | 8000 | Django API |
| `redis` | — | Брокер Celery |
| `celery` | — | Worker (prefork, concurrency=5) |
| `celery_beat` | — | Планировщик периодических задач |

Миграции (при первом запуске):

```bash
docker compose exec web python manage.py migrate
```

Документация API:

- Swagger: http://127.0.0.1:8000/swagger/
- ReDoc: http://127.0.0.1:8000/redoc/

## Локальная разработка

**Требования:** Python 3.12+, Redis

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

cd review_parser
python manage.py migrate
python manage.py runserver
```

В отдельных терминалах:

```bash
# из корня проекта, с активированным venv
celery -A review_parser worker --loglevel=info --concurrency=3
celery -A review_parser beat --loglevel=info
```

Для локального запуска без Docker задайте брокер Redis:

```bash
export CELERY_BROKER_URL=redis://127.0.0.1:6379/0
```

## API

Базовый путь: `/api/v1/`

### GET `/api/v1/reviews/`

Получить отзывы филиала по провайдеру.

Query-параметры:

| Параметр | Тип | Описание |
|----------|-----|----------|
| `branch_id` | int | ID филиала |
| `provider` | string | `yandex`, `2gis`, `vlru`, `google` |
| `limit` | int | Лимит (1–500, по умолчанию 50) |
| `offset` | int | Смещение (по умолчанию 0) |

```bash
curl "http://127.0.0.1:8000/api/v1/reviews/?branch_id=1&provider=yandex&limit=10"
```

### POST `/api/v1/sync/`

Запустить асинхронный парсинг. Ответ **202 Accepted**.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sync/ \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": 1,
    "branch_id": 1,
    "providers": ["yandex", "2gis", "vlru"]
  }'
```

Пример ответа:

```json
{
  "task_id": "a3f2c1b0-4d8d-4e2a-9f1b-2c8d7e6f5a4b",
  "status": "PENDING"
}
```

Пример итогового результата задачи:

```json
{
  "yandex": {"parsed": 553, "created": 553},
  "2gis": {"parsed": 917, "created": 917},
  "vlru": {"parsed": 324, "created": 324}
}
```

Ошибки по отдельным провайдерам не отменяют задачу целиком:

```json
{
  "yandex": {"error": "branch_platform_not_found", "provider": "yandex"},
  "2gis": {"parsed": 10, "created": 3}
}
```

### GET `/api/v1/tasks/`

Проверить статус Celery-задачи.

```bash
curl "http://127.0.0.1:8000/api/v1/tasks/?task_id=<uuid>"
```

Статусы: `PENDING`, `STARTED`, `SUCCESS`, `FAILURE`, `RETRY`, `REVOKED`.

Результат выполненной задачи доступен через Celery result backend (`django_celery_results`) или `AsyncResult(task_id).result`.

## Модель данных

```
Organization (ИНН, название)
    └── Branch (адрес)
            └── BranchPlatform (provider, url, review_count, review_avg)
                    └── Review (author, rating, content, published_date, ...)
```

Перед синхронизацией для филиала должны существовать записи `BranchPlatform` с заполненным `url` для каждого запрашиваемого провайдера.

## Провайдеры

| Provider | Парсер | Примечание |
|----------|--------|------------|
| `yandex` | Playwright + Chromium | Headless-браузер в Docker |
| `2gis` | HTTP API | |
| `vlru` | HTTP + HTML | |

## Тесты

```bash
cd review_parser
pytest
```

## Линтинг и pre-commit

```bash
pip install -r requirements-dev.txt
pre-commit install
ruff check review_parser
ruff format review_parser
```

## Структура проекта

```
.
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── review_parser/
    ├── manage.py
    ├── common_parser/
    │   ├── models.py          # Organization, Branch, Review, ...
    │   ├── views.py           # API endpoints
    │   ├── tasks.py           # Celery tasks (chord, парсинг)
    │   ├── parsers/           # Yandex, 2GIS, VL.ru
    │   └── tests/
    └── review_parser/
        ├── settings.py
        ├── celery.py
        └── urls.py
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | URL брокера Redis |
| `DJANGO_SETTINGS_MODULE` | `review_parser.settings` | Модуль настроек Django |

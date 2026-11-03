# SkyGuard

Прототип платформи керованого обміну геоданими про укриття: реєстр укриттів, статус від комендантів і краудсорс-звіти громадян з перевіркою якості даних, згода на обробку ПДн і незмінний журнал аудиту.

Командний проєкт, група ОІ-33, Національний університет «Львівська політехніка».

## Швидкий старт (Docker)

```bash
cp .env.example .env        # змініть POSTGRES_PASSWORD
docker compose up -d --build
```

- API: http://localhost:8000
- Документація OpenAPI: http://localhost:8000/docs
- Перевірка стану: http://localhost:8000/health/ready

Міграції застосовуються автоматично при старті контейнера `api`.

## Локальна розробка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d db
export POSTGRES_HOST=localhost
alembic upgrade head
uvicorn app.main:app --reload
```

Тести (потребують запущеної БД з міграцією; без неї запуск завершиться помилкою):

```bash
pytest -q --cov=app        # 19 тестів, звіт покриття (поріг 70%)
ruff check . && ruff format --check .
```

## Структура

```
app/
  api/routes/     маршрути FastAPI
  core/config.py  налаштування з .env
  db/             підключення, базовий клас моделей
  models/         Shelter, User, Role, ConsentRecord, StatusReport, AuditLog
migrations/       Alembic; 0001 — початкова схема, тригери аудиту, ролі
tests/            тести API і гарантій схеми
docs/
  stack.md        стек і архітектурні рішення
  db-schema.md    ER-діаграма, таблиці, обмеження, класифікація
  nfr.md          нефункціональні вимоги
frontend/         Leaflet-клієнт (SG-9)
```

## Документація

- [Технологічний стек](docs/stack.md)
- [Схема бази даних](docs/db-schema.md)
- [Нефункціональні вимоги](docs/nfr.md)

## Команда і задачі

Беклог у Jira, проєкт `SKYG`. Ця основа закриває SG-19; далі на ній будуються SG-10 (ядро API і RBAC), SG-11 (Audit Trail), SG-21 (статуси, DQ, WebSocket), SG-24 (запуск з нуля).

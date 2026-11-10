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

Демо-дані (8 укриттів Львова і по одному користувачу на роль):

```bash
docker compose exec api python -m app.seed
```

| Email | Роль | Пароль |
|---|---|---|
| `citizen@skyguard.demo` | CITIZEN | `skyguard-demo` |
| `volunteer@skyguard.demo` | VERIFIED_VOLUNTEER | `skyguard-demo` |
| `manager@skyguard.demo` | SHELTER_MANAGER (укриття DEMO-0001) | `skyguard-demo` |
| `dsns@skyguard.demo` | DSNS_OPERATOR | `skyguard-demo` |
| `auditor@skyguard.demo` | SECURITY_AUDITOR | `skyguard-demo` |

У `/docs` натисніть **Authorize** і вставте `access_token` з `POST /api/v1/auth/login`.

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
pytest -q --cov=app        # звіт покриття (поріг 70%)
ruff check . && ruff format --check .
```

## Структура

```
app/
  api/deps.py     шлюз доступу: автентифікація → роль → згода, аудит відмов
  api/routes/     маршрути: auth, consents, shelters, health
  core/           налаштування, JWT і паролі, політики доступу (RBAC), формат помилок
  db/             підключення, базовий клас моделей
  models/         Shelter, User, Role, ConsentRecord, StatusReport, AuditLog
  schemas/        моделі запитів і відповідей (GeoJSON)
  services/       аудит, згода, геообчислення (Haversine)
  seed.py         демо-дані
migrations/       Alembic: 0001 — схема і тригери аудиту, 0002 — довідники за SG-2
tests/            тести API і гарантій схеми на справжньому PostgreSQL
docs/
  api.md          контракт API: ендпоінти, помилки, матриця доступу
  openapi.json    специфікація OpenAPI для фронтенду
  stack.md        стек і архітектурні рішення
  db-schema.md    ER-діаграма, таблиці, обмеження, класифікація
  nfr.md          нефункціональні вимоги
scripts/          службові скрипти (експорт OpenAPI)
frontend/         Leaflet-клієнт (SG-9)
```

## Документація

- [Контракт API](docs/api.md) і [OpenAPI](docs/openapi.json)
- [Технологічний стек](docs/stack.md)
- [Схема бази даних](docs/db-schema.md)
- [Нефункціональні вимоги](docs/nfr.md)

## Команда і задачі

Беклог у Jira, проєкт `SKYG`. Зроблено: SG-19 (основа, схема БД), SG-10 (автентифікація, RBAC-шлюз, згода, публічний реєстр). Далі: SG-21 (статуси, DQ, WebSocket), інтеграція SG-11 (консоль аудитора), SG-24 (запуск з нуля).

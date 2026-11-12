# 🛡️ SkyGuard — Data Governance by Design
### Платформа керованого обміну геопросторовими даними про укриття та цивільний захист

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20Alpine-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-199900?logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Про проєкт

**SkyGuard** — інформаційна система керованого обміну геопросторовими даними про фонд захисних споруд цивільного захисту.

Система реалізує концепцію **Data Governance by Design**:
* **Чотирирівнева класифікація даних:**
  * `L1: PUBLIC` — реєстр укриттів, адреси, координати входів, доступність;
  * `L2: INTERNAL` — телеметрія електронних замків Smart Lock (заряд, сигнал зв'язку);
  * `L3: CONFIDENTIAL` — контакти комендантів, журнали інцидентів, зведення завантаженості;
  * `L4: SENSITIVE` — точні GPS-координати користувачів (обробка лише за активною згодою Opt-in).
* **Контроль якості даних (Data Quality):**
  * `DQ-1: Geofence` — підтвердження стану дверей укриття дозволено лише в радіусі $\le 100\text{ м}$ (Haversine);
  * `DQ-2: Freshness` — автоматичне визначення застарілих статусів ($> 30\text{ хв}$);
  * `DQ-3: Quorum` — зміна публічного статусу за кворумом від 3 незалежних свідків (із захистом від накрутки: 1 підтвердження на пристрій за 15 хв).
* **Незмінний журнал аудиту:**
  * Усі події (надання/відкликання згоди, відхилення доступу 403, помилки якості 422, зміна статусів) фіксуються в криптографічному журналі з хеш-ланцюгом **SHA-256**.

---

## 🚀 Як запустити проєкт

### Варіант 1. Швидкий запуск через Docker Compose (Рекомендовано)

Запуск повної інфраструктури (БД PostgreSQL 16 + FastAPI бекенд + веб-клієнт):

```bash
# 1. Створіть файл змінних оточення з шаблону
cp .env.example .env

# 2. Запустіть сервіси
docker compose up -d --build

# 3. Наповніть базу демонстраційними укриттями та тестовими користувачами
docker compose exec api python -m app.seed
```

**Адреси сервісів:**
* 🗺️ **Веб-інтерфейс (карта):** [http://localhost:8085](http://localhost:8085)
* ⚡ **REST API:** [http://localhost:8000](http://localhost:8000)
* 📖 **OpenAPI документація (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
* 🩺 **Health Check:** [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

---

### Варіант 2. Локальний запуск веб-інтерфейсу (без Docker)

Веб-клієнт є автономним і може працювати на вбудованому каталозі укриттів:

```bash
# Запуск локального HTTP-сервера для папки фронтенду
python3 -m http.server 8085 --directory frontend
```
Після цього відкрийте у браузері: [http://localhost:8085](http://localhost:8085) або просто відкрийте файл `frontend/index.html`.

---

### Варіант 3. Локальний запуск бекенду (Python)

```bash
# 1. Віртуальне оточення
python3 -m venv .venv
source .venv/bin/activate

# 2. Встановлення залежностей
pip install -r requirements-dev.txt

# 3. Запуск PostgreSQL (наприклад, через Docker)
docker compose up -d db

# 4. Застосування міграцій та наповнення БД
alembic upgrade head
python -m app.seed

# 5. Запуск сервера розробки FastAPI
uvicorn app.main:app --reload --port 8000
```

---

## 👤 Тестові облікові записи (RBAC)

Для демонстрації рольової моделі доступу створено попередньо налаштовані профілі:

> **Пароль для всіх службових ролей:** `skyguard-demo`

| Роль | Рівень доступу | Email (Логін) | Пароль | Можливості в системі |
|:---|:---|:---|:---|:---|
| **Громадянин** *(Citizen)* | L1: PUBLIC | `citizen@skyguard.demo` | `skyguard-demo` | Пошук укриттів, пішохідна навігація SafeRoute, краудсорс-підтвердження |
| **Верифікований волонтер** *(Volunteer)* | L1 / L2 | `volunteer@skyguard.demo` | `skyguard-demo` | Підтвердження статусів укриттів із підвищеною вагою голосу |
| **Комендант укриття** *(Manager)* | L2 / L3 | `manager@skyguard.demo` | `skyguard-demo` | Керування закріпленим укриттям (`DEMO-0001`), відкриття замків Smart Lock |
| **Оператор ДСНС** *(Operator)* | L3 / L4 | `dsns@skyguard.demo` | `skyguard-demo` | Моніторинг заповненості укриттів, контакти, оперативна зміна статусу |
| **Аудитор безпеки** *(Auditor)* | L3 / L4 | `auditor@skyguard.demo` | `skyguard-demo` | Перегляд криптографічного журналу аудиту (SHA-256), розслідування інцидентів |

*(Перемикання ролей доступне в 1 клік через іконку профілю `👤` у верхній шапці).*

---

## 🧪 Запуск автоматичних тестів

```bash
# Запуск юніт-тестів та інтеграційних тестів із перевіркою покриття
pytest -v --cov=app

# Перевірка стилю коду та лінтер Ruff
ruff check . && ruff format --check .
```

---

## 📂 Структура репозиторію

```text
├── app/                        # Вихідний код бекенду (FastAPI)
│   ├── api/                    # Маршрути API (auth, consents, shelters, ws, health, alerts)
│   │   └── deps.py             # Шлюз безпеки: автентифікація → перевірка RBAC → згода L4
│   ├── core/                   # Налаштування середовища, JWT-токени, політики доступу
│   ├── db/                     # Підключення до PostgreSQL (SQLAlchemy 2.0)
│   ├── models/                 # ORM-моделі: Shelter, User, Role, ConsentRecord, AuditLog
│   ├── schemas/                # Валідація Pydantic (GeoJSON RFC 7946, DTO)
│   ├── services/               # Бізнес-логіка: гаверсинус (DQ-1), кворум (DQ-3), аудит SHA-256
│   └── seed.py                 # Генерація первинних демо-даних (укриття, ролі)
├── frontend/                   # Мобільний та веб-інтерфейс (Leaflet 1.9, Vanilla JS/CSS)
│   ├── css/styles.css          # Стилі, адаптивна верстка, Bottom Sheet, Mobile Header
│   ├── js/                     # Модульна архітектура клієнта:
│   │   ├── api.js              # REST-клієнт та взаємодія з бекендом
│   │   ├── audit.js            # Інтерактивна консоль аудиту подій SHA-256
│   │   ├── config.js           # Координати укриттів, параметри конфігурації
│   │   ├── crowdsource.js      # Подача звітів громадян з перевіркою Geofence
│   │   ├── geo.js              # Розрахунок відстаней (Haversine), пішохідні маршрути OSRM
│   │   ├── map.js              # Ініціалізація карти Leaflet, WGS-84 шари, маркери
│   │   ├── security.js         # Керування згодою Opt-in, перемикач ролей, інциденти 403
│   │   ├── state.js            # Централізований стан клієнтської сесії
│   │   └── ui.js               # Керування модальними вікнами, картками укриттів, тостами
│   └── index.html              # Розмітка веб-застосунку
├── migrations/                 # Міграції бази даних (Alembic)
├── tests/                      # Автоматизовані тести pytest (TC-01..TC-06, RBAC, DQ-1..DQ-3)
├── docs/                       # Технічна документація (API, схема БД, NFR, архітектура)
├── docker-compose.yml          # Оркестрація контейнерів (db, api, frontend)
├── Dockerfile                  # Збірка контейнера бекенду
└── README.md                   # Документація проєкту
```

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
  * `DQ-3: Quorum` — зміна публічного статусу, коли сума ваг звітів за 15 хв сягає 3 (мешканець — 1, волонтер/комендант/ДСНС — 3); не більше 3 звітів від користувача за 5 хв.
* **Незмінний журнал аудиту:**
  * Усі події (надання/відкликання згоди, відхилення доступу 403, помилки якості 422, зміна статусів) фіксуються в криптографічному журналі з хеш-ланцюгом **SHA-256**.

---

## 🚀 Запуск з нуля

Увесь прототип (PostgreSQL 16 + FastAPI + веб-клієнт) піднімається **однією командою**. Під час першого старту API сам застосовує міграції й засіває демо-укриття та тестових користувачів. Окремо нічого запускати не треба.

### 1. Що потрібно встановити (один раз)

| Програма | Навіщо | Де взяти |
|:---|:---|:---|
| **Git** | завантажити репозиторій | https://git-scm.com/downloads |
| **Docker Desktop** (Windows/macOS) або Docker Engine + Compose v2.24+ (Linux) | запуск БД, API і фронтенду | https://www.docker.com/products/docker-desktop/ |

Python для запуску **не потрібен**. Він знадобиться лише для тестів і перевірочного скрипта (див. нижче).

> **Windows.** Docker Desktop працює через WSL 2, і йому потрібні компоненти Windows, які вмикаються лише з правами адміністратора. Якщо інсталятор або Docker Desktop пише *«Virtual Machine Platform is not enabled»*, відкрийте **PowerShell від імені адміністратора** і виконайте:
> ```powershell
> Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart
> Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -All -NoRestart
> ```
> Потім **перезавантажте ПК**, виконайте `wsl --update` і знову запустіть Docker Desktop. Перед запуском проєкту внизу зліва в Docker Desktop має бути **«Engine running»**.

### 2. Завантажити й запустити

Ці команди однакові для PowerShell, cmd, macOS і Linux:

```bash
git clone https://github.com/Taras-Klichkovskyi/skyguard.git
cd skyguard
docker compose up -d --build --wait
```

Перший запуск триває 3–5 хвилин, бо Docker завантажує образи. Команда завершиться, коли всі три сервіси будуть готові.

Файл `.env` створювати **не обов'язково**: без нього діють безпечні для демо значення за замовчуванням. Якщо треба змінити паролі, порти чи CORS, скопіюйте шаблон і відредагуйте його:

| Оболонка | Команда |
|:---|:---|
| PowerShell | `Copy-Item .env.example .env` |
| cmd | `copy .env.example .env` |
| bash / zsh | `cp .env.example .env` |

### 3. Відкрити

* 🗺️ **Веб-інтерфейс (карта):** http://localhost:8085
* ⚡ **REST API:** http://localhost:8000
* 📖 **Swagger (OpenAPI):** http://localhost:8000/docs
* 🩺 **Стан API і БД:** http://localhost:8000/health/ready

### 4. Перевірити, що все працює (необов'язково)

```bash
python scripts/check_stack.py
```

Скрипт не потребує жодних пакетів. Він перевіряє:
- API і БД;
- наявність укриттів;
- веб-інтерфейс;
- CORS між фронтендом і API;
- вхід усіх п'яти тестових користувачів;
- цілісність журналу аудиту.

Кожна проблема виводиться з підказкою, що робити. Ту саму перевірку на чистій машині без `.env` виконує CI (job `compose-smoke`).

### Зупинити, перезапустити, почати з чистої бази

```bash
docker compose ps          # стан сервісів
docker compose logs api    # логи API (міграції, засів, помилки)
docker compose down        # зупинити (дані зберігаються)
docker compose down -v     # зупинити й видалити БД — наступний up засіє все заново
git pull && docker compose up -d --build --wait   # оновитися до нової версії
```

---

## 👤 Тестові користувачі (RBAC)

Створюються автоматично під час першого старту. **Пароль для всіх:** `skyguard-demo`.

| Роль | Email (логін) | Рівень доступу | Що може в системі |
|:---|:---|:---|:---|
| **Громадянин** *(CITIZEN)* | `citizen@skyguard.demo` | L1: PUBLIC | Пошук укриттів, маршрут SafeRoute, краудсорс-звіт біля входу (вага 1) |
| **Верифікований волонтер** *(VERIFIED_VOLUNTEER)* | `volunteer@skyguard.demo` | L1 / L2 | Звіт з вагою 3: сам закриває кворум DQ-3 |
| **Комендант укриття** *(SHELTER_MANAGER)* | `manager@skyguard.demo` | L2 / L3 | Офіційний статус свого укриття (`DEMO-0001`), службові контакти |
| **Оператор ДСНС** *(DSNS_OPERATOR)* | `dsns@skyguard.demo` | L3 | Примусова зміна статусу будь-якого укриття, контакти комендантів |
| **Аудитор безпеки** *(SECURITY_AUDITOR)* | `auditor@skyguard.demo` | L3 | Журнал аудиту SHA-256 з перевіркою цілісності на сервері |

**Як увійти у веб-інтерфейсі:**
1. Угорі праворуч натисніть кнопку з поточною роллю (**👤 Громадянин ▾**).
2. На вкладці **«Швидкий вибір ролі»** натисніть **🔑 Увійти з паролем** на картці потрібної ролі. Нижче з'явиться блок підтвердження з уже вписаним паролем.
3. Натисніть **«Підтвердити»** або Enter.

Можна й інакше: на вкладці **«Вхід за обліковим записом (JWT)»** введіть email і пароль з таблиці.

Через API вхід виконується так: `POST /api/v1/auth/login` з тілом `{"email": "...", "password": "skyguard-demo"}`. У відповіді приходить `access_token` (15 хв) і `refresh_token`.

---

## 🩹 Якщо щось не працює

| Що бачите | Причина і що робити |
|:---|:---|
| `docker: command not found` / `'docker' is not recognized` | Docker Desktop не встановлено або термінал відкрито до встановлення. Закрийте й знову відкрийте термінал |
| `error during connect` / `Cannot connect to the Docker daemon` | Docker Desktop не запущено. Запустіть його й дочекайтеся «Engine running» |
| *Virtual Machine Platform is not enabled* | Див. примітку для Windows у кроці 1 (потрібні права адміністратора й перезавантаження) |
| *Virtualization support not detected* | У BIOS/UEFI вимкнена віртуалізація: увімкніть **Intel VT-x** або **AMD SVM** |
| `port is already allocated` (5432) | Порт зайнятий локальним PostgreSQL. Скопіюйте `.env.example` у `.env`, поставте `DB_PORT=5433` і `POSTGRES_PORT=5433`, потім знову `docker compose up -d --wait` |
| `port is already allocated` (8000 або 8085) | Зайнято іншою програмою, наприклад старим `uvicorn` або `http.server`. Закрийте її |
| Помилка про `env_file`, `path` чи `required` | Застарілий Docker Compose (до v2.24). Оновіть Docker Desktop |
| Карта є, але вхід не працює або з'являється «API недоступний» | API не запущено (`docker compose ps`, `docker compose logs api`) або старий `.env` без `http://localhost:8085` у `CORS_ORIGINS`. Видаліть `.env` або скопіюйте шаблон наново, потім `docker compose up -d` |
| У консолі браузера `ERR_BLOCKED_BY_CLIENT` | Блокувальник реклами (uBlock тощо) не пускає запити до API. Вимкніть його для `localhost` |
| Карта сіра, без вулиць | Немає інтернету: Leaflet і тайли OpenStreetMap завантажуються з мережі |
| Старі статуси чи записи аудиту від попередніх запусків | `docker compose down -v && docker compose up -d --wait` — база створиться й засіється наново |
| `Set-ExecutionPolicy` / `Activate.ps1` не виконується (PowerShell) | Перед активацією `.venv` виконайте `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. У cmd замість цього використовуйте `.venv\Scripts\activate.bat` |

---

## 🧪 Автоматичні тести

Тести працюють проти справжнього PostgreSQL, тому БД має бути запущена:

```bash
docker compose up -d db --wait
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1   ·   cmd: .venv\Scripts\activate.bat   ·   bash: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
pytest -v --cov=app             # тести й покриття (поріг 70 %)
ruff check . && ruff format --check .
```

Рекомендований Python — 3.12 або 3.13. На найновіших версіях Python під Windows деякі пакети можуть ще не мати готових збірок.

Без Docker можна вказати будь-який PostgreSQL 16 повним рядком підключення: `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db`.

---

## 🧰 Інші способи запуску

**Лише веб-інтерфейс (офлайн-демо без сервера).** Клієнт має вбудований каталог укриттів і працює без API. Ролі в ньому перемикаються локально, і на це вказує повідомлення «API недоступний».
```bash
python -m http.server 8085 --directory frontend
```

**API на хості з автоперезавантаженням (для розробки).** Потрібні `.env` (`POSTGRES_HOST=localhost` вже в шаблоні) і запущена БД:
```bash
docker compose up -d db --wait
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload --port 8000
```

**Демо-відео (SG-17).** Кадри знімаються автоматично проти запущеного стеку: `python scripts/demo/record_demo.py`, потім `python scripts/demo/compose_video.py demo_capture.zip`. Подробиці в документації самих скриптів.

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
│   ├── index.html              # Розмітка веб-застосунку
│   └── styles.css              # Стилі, адаптивна верстка, Bottom Sheet, Mobile Header
├── migrations/                 # Міграції бази даних (Alembic)
├── scripts/
│   ├── check_stack.py          # Перевірка, що весь стек піднявся (SG-24)
│   └── demo/                   # Зйомка й монтаж демо-відео (SG-17)
├── tests/                      # Автоматизовані тести pytest (TC-01..TC-06, RBAC, DQ-1..DQ-3)
├── docs/                       # Технічна документація (API, схема БД, NFR, архітектура)
├── docker-compose.yml          # Увесь стек однією командою (db, api, frontend)
├── .env.example                # Необов'язкові налаштування (паролі, порти, CORS)
├── Dockerfile                  # Збірка контейнера бекенду
└── README.md                   # Документація проєкту
```

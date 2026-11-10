# Контракт API SkyGuard (SG-10, SG-21)

Базова адреса: `http://localhost:8000`. Інтерактивна документація: `/docs`, специфікація: [`openapi.json`](openapi.json).
Формат обміну — JSON, час — UTC (ISO 8601), геодані — GeoJSON за RFC 7946: координати `[довгота, широта]`, WGS84.

## Ендпоінти

| Метод і шлях | Призначення | Доступ |
|---|---|---|
| `GET /api/v1/shelters` | Публічний реєстр укриттів, `FeatureCollection` | без токена |
| `GET /api/v1/shelters/{id}` | Одне укриття, `Feature` | без токена |
| `POST /api/v1/shelters/nearby` | Найближчі укриття за GPS користувача | токен + згода `ROUTE_GPS` |
| `GET /api/v1/shelters/{id}/contacts` | Контакти коменданта (CONFIDENTIAL) | `DSNS_OPERATOR`; `SHELTER_MANAGER` — лише своє укриття |
| `POST /api/v1/shelters/{id}/status` | Офіційний статус укриття, застосовується одразу | `DSNS_OPERATOR`; `SHELTER_MANAGER` — лише своє укриття |
| `POST /api/v1/shelters/{id}/reports` | Краудсорс-звіт про стан укриття | `CITIZEN`, `VERIFIED_VOLUNTEER` + згода `REPORT_GEOFENCE` |
| `WS /ws/v1/shelters` | Потік змін статусу для мапи | без токена |
| `POST /api/v1/auth/register` | Самореєстрація, роль завжди `CITIZEN` | без токена |
| `POST /api/v1/auth/login` | Видає access- і refresh-токен | без токена |
| `POST /api/v1/auth/refresh` | Нова пара токенів за refresh-токеном | без токена |
| `GET /api/v1/auth/me` | Поточний користувач і його роль | токен |
| `GET /api/v1/consents` | Стан згоди за кожною ціллю | токен |
| `POST /api/v1/consents` | Надати згоду на одну ціль | токен |
| `DELETE /api/v1/consents/{purpose}` | Відкликати згоду | токен |
| `GET /health/live`, `GET /health/ready` | Перевірки стану | без токена |

Параметри `GET /api/v1/shelters`: `bbox=min_lon,min_lat,max_lon,max_lat`, `status`, `ramp`, `generator`, `starlink`, `water`, `limit`.

Координати для `POST /shelters/nearby` передаються в тілі запиту, а не в адресі, щоб не осідати в журналах доступу. Сервер їх не зберігає.

## Автентифікація

```http
POST /api/v1/auth/login
{"email": "citizen@skyguard.demo", "password": "skyguard-demo"}

200 OK
{"access_token": "…", "refresh_token": "…", "token_type": "bearer", "expires_in": 900, "role": "CITIZEN"}
```

Далі кожен захищений запит несе заголовок `Authorization: Bearer <access_token>`.
Access-токен живе 15 хв, refresh — 7 днів. У токені є ідентифікатор і роль, але права сервер
визначає за роллю з бази: зміна ролі чи блокування користувача діють одразу.

## Шлюз доступу

Усі захищені ендпоінти проходять однакові перевірки в такому порядку:

1. **Автентифікація.** Немає токена, він прострочений або підроблений → `401`.
2. **Роль.** Роль не входить до політики дії або ресурс не закріплений за користувачем → `403`.
3. **Згода.** Дія обробляє GPS, а активної згоди на цю ціль немає → `403`.

Кожна відмова спершу записується в незмінний журнал аудиту, і лише потім клієнт отримує відповідь
з номером запису `audit_entry_id`.

### Матриця доступу

| Дія (політика) | Клас даних | Anonymous | Citizen | Volunteer | Shelter Manager | DSNS Operator | Security Auditor |
|---|---|---|---|---|---|---|---|
| Читати реєстр укриттів | L1 PUBLIC | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `SHELTER_READ_CONTACTS` | L3 CONFIDENTIAL | 401 | 403 | 403 | ✓ своє | ✓ | 403 |
| `SHELTER_NEARBY_SEARCH` | L4 SENSITIVE | 401 | ✓ зі згодою | ✓ зі згодою | ✓ зі згодою | ✓ зі згодою | 403 |
| `CONSENT_MANAGE_OWN` | L4 SENSITIVE | 401 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `SHELTER_STATUS_UPDATE` | L1 PUBLIC | 401 | 403 | 403 | ✓ своє | ✓ | 403 |
| `SHELTER_STATUS_REPORT` | L4 SENSITIVE | 401 | ✓ зі згодою | ✓ зі згодою | 403 | 403 | 403 |

Політики описані даними в `app/core/policy.py`; ендпоінти лише посилаються на них.

## Формат помилок

```json
{
  "error": "DENIED_403_RBAC",
  "message": "Ваша роль не має доступу до цих даних",
  "reason": "role_not_allowed",
  "role": "CITIZEN",
  "required_roles": ["DSNS_OPERATOR", "SHELTER_MANAGER"],
  "data_classification": "CONFIDENTIAL",
  "audit_entry_id": 176,
  "request_id": "0246b3cdaff64882a40f76c4b2912587"
}
```

`error`, `message` і `request_id` є в кожній помилці. `request_id` дублюється в заголовку `X-Request-ID`
і в записі аудиту.

| HTTP | `error` | Коли | Додаткові поля |
|---|---|---|---|
| 401 | `DENIED_401_AUTH` | Немає або недійсний токен, хибний логін чи пароль | `reason`: `token_missing`, `token_expired`, `token_invalid`, `token_wrong_type`, `user_inactive`, `bad_credentials`; `audit_entry_id` |
| 403 | `DENIED_403_RBAC` | Роль не має прав або ресурс чужий | `reason`: `role_not_allowed`, `not_resource_owner`; `role`, `required_roles`, `data_classification`, `audit_entry_id` |
| 403 | `DENIED_403_CONSENT` | Немає активної згоди | `required_consent`, `data_classification`, `audit_entry_id` |
| 404 | `SHELTER_NOT_FOUND`, `CONSENT_NOT_ACTIVE`, `NOT_FOUND` | Ресурсу немає | |
| 409 | `EMAIL_TAKEN` | Email уже зареєстровано | |
| 422 | `VALIDATION_ERROR` | Запит не пройшов перевірку формату | `details`: список `{field, problem}` |
| 422 | `GEOLOCATION_OUT_OF_BOUNDS` | DQ-1: репортер далі ніж за 100 м від укриття | `rule`, `distance_m`, `max_distance_m`, `report_id`, `audit_entry_id` |
| 422 | `STALE_DATA` | DQ-2: спостереженню понад 30 хв | `rule`, `age_min`, `max_age_min`, `report_id`, `audit_entry_id` |
| 429 | `RATE_LIMITED` | Понад 3 звіти за 5 хв від одного користувача | заголовок `Retry-After`, `audit_entry_id` |

Коди `error` для відмов доступу збігаються з типами подій у журналі аудиту.
Код для DQ-1 взято з критеріїв SG-21 і тест-кейсу TC-04. У розділах 2.4 і 4.1 звіту ще стоять
`DQ_GEOFENCE_FAILED` і `DATA_QUALITY_RULE_VIOLATION` — їх треба замінити на `GEOLOCATION_OUT_OF_BOUNDS`.

## Згода

Цілі: `ROUTE_GPS` (маршрут і пошук найближчого укриття), `REPORT_GEOFENCE` (перевірка присутності
біля укриття для звіту), `SOS`. Стани: `NOT_GRANTED`, `ACTIVE`, `REVOKED`, `EXPIRED`.

- Згода гранулярна: дозвіл на одну ціль не поширюється на інші.
- `POST /consents` повертає `201`, якщо згоду створено, і `200`, якщо вона вже була активна.
- Відкликання діє одразу: наступний запит, що потребує цієї згоди, отримає `403`.
- Записи не видаляються: відкликання ставить дату, повторна згода створює новий запис.
- Відмова від згоди не обмежує перегляд публічної мапи.

## Зміна статусу укриття

### Офіційний статус

```http
POST /api/v1/shelters/{id}/status
{"status": "FULL", "occupancy": 850, "comment": "Місць немає"}
```

`status`: `OPEN`, `FULL` або `CLOSED`. `occupancy` і `comment` необов'язкові. Статус застосовується
одразу, а звіти мешканців про це укриття, що чекали кворуму, знімаються з розгляду.

### Краудсорс-звіт

```http
POST /api/v1/shelters/{id}/reports
{"status": "CLOSED", "latitude": 49.83975, "longitude": 24.02975, "observed_at": "2026-11-11T08:15:00Z"}
```

`observed_at` необов'язкове (типово — час отримання) і мусить мати часовий пояс. Звіт проходить
правила якості в такому порядку:

| Правило | Умова | Якщо порушено |
|---|---|---|
| DQ-2 свіжість | від спостереження минуло ≤ 30 хв | `422 STALE_DATA` |
| DQ-1 геоприв'язка | відстань Haversine до укриття ≤ 100 м | `422 GEOLOCATION_OUT_OF_BOUNDS` |
| DQ-3 кворум | сума ваг незалежних звітів з однаковим статусом за 15 хв ≥ 3 | звіт чекає, `applied: false` |

Вага звіту: мешканець — 1; верифікований волонтер, комендант і оператор ДСНС — 3. Тобто статус
змінюють три різні мешканці або один волонтер. Один користувач — один голос: його новий звіт про
те саме укриття замінює попередній. Звіти з різними статусами не додаються. Якщо кворум не зібрано
за 15 хв, звіт анулюється (`EXPIRED`) і публічний статус не змінюється.

Відповідь `200` в обох ендпоінтах:

```json
{
  "report_id": "…",
  "shelter_id": "…",
  "reported_status": "CLOSED",
  "applied": false,
  "validation_status": "QUORUM_PENDING",
  "distance_m": 7.1,
  "quorum": {"collected": 1, "required": 3, "window_min": 15},
  "shelter": { "type": "Feature", "…": "поточний публічний стан укриття" }
}
```

Для `applied: false` клієнт показує «Потребує підтвердження». `validation_status`: `ACCEPTED`,
`QUORUM_PENDING`; у збережених звітах також `REJECTED` і `EXPIRED`.

Координати репортера використовуються лише для обчислення відстані й **не зберігаються**:
у базу потрапляє тільки `distance_m`. Відхилені звіти теж зберігаються — для аналізу якості даних.

## Сповіщення через WebSocket

```js
const ws = new WebSocket("ws://localhost:8000/ws/v1/shelters");
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === "shelter.updated") updateMarker(msg.shelter); // GeoJSON Feature
};
setInterval(() => ws.send("ping"), 30000); // сервер відповість {"type": "pong"}
```

Після підключення сервер надсилає `{"type": "connected", "events": ["shelter.updated"], "server_time": "…"}`.
Подія приходить після кожної **застосованої** зміни статусу, тобто після успішного запису в базу й журнал аудиту:

```json
{"type": "shelter.updated", "source": "OFFICIAL", "sent_at": "2026-11-11T08:15:02Z", "shelter": { "type": "Feature", "…": "…" }}
```

`source`: `OFFICIAL` або `CROWDSOURCE`. `shelter` — те саме публічне подання, що й у `GET /shelters/{id}`,
тому токен для підписки не потрібен. Звіти, що чекають кворуму чи відхилені, подій не породжують.

## Що записується в журнал аудиту

| Подія | Результат |
|---|---|
| `DENIED_401_AUTH`, `DENIED_403_RBAC`, `DENIED_403_CONSENT` | DENIED |
| `USER_REGISTERED`, `LOGIN_SUCCESS` | SUCCESS |
| `CONSENT_GRANTED`, `CONSENT_REVOKED` | SUCCESS |
| `SHELTER_READ_CONTACTS`, `SHELTER_NEARBY_SEARCH` | SUCCESS |
| `UPDATE_STATUS_VERIFIED` (статус змінено), `UPDATE_STATUS_PENDING` (звіт чекає кворуму) | SUCCESS |
| `FAILED_DQ_422`, `RATE_LIMITED_429` | DENIED |

Успішна дія і її запис аудиту зберігаються однією транзакцією. У журнал не потрапляють паролі,
токени, email і координати; IP зберігається лише як HMAC-SHA-256. Читання публічного реєстру не журналюється.

## Приклад для фронтенду

```js
const API = "http://localhost:8000/api/v1";

// 1. Мапа: без токена
const shelters = await (await fetch(`${API}/shelters?bbox=23.9,49.78,24.1,49.9`)).json();
L.geoJSON(shelters).addTo(map);

// 2. Вхід
const { access_token } = await (await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
})).json();
const auth = { Authorization: `Bearer ${access_token}`, "Content-Type": "application/json" };

// 3. Модалка згоди
await fetch(`${API}/consents`, { method: "POST", headers: auth, body: JSON.stringify({ purpose: "ROUTE_GPS" }) });

// 4. Найближчі укриття; 403 → показати модалку згоди або екран відмови
const r = await fetch(`${API}/shelters/nearby`, {
  method: "POST", headers: auth, body: JSON.stringify({ latitude, longitude, limit: 5 }),
});
if (r.status === 403) {
  const { error, audit_entry_id } = await r.json(); // DENIED_403_CONSENT або DENIED_403_RBAC
}
```

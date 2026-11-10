# Контракт API SkyGuard (SG-10)

Базова адреса: `http://localhost:8000`. Інтерактивна документація: `/docs`, специфікація: [`openapi.json`](openapi.json).
Формат обміну — JSON, час — UTC (ISO 8601), геодані — GeoJSON за RFC 7946: координати `[довгота, широта]`, WGS84.

## Ендпоінти

| Метод і шлях | Призначення | Доступ |
|---|---|---|
| `GET /api/v1/shelters` | Публічний реєстр укриттів, `FeatureCollection` | без токена |
| `GET /api/v1/shelters/{id}` | Одне укриття, `Feature` | без токена |
| `POST /api/v1/shelters/nearby` | Найближчі укриття за GPS користувача | токен + згода `ROUTE_GPS` |
| `GET /api/v1/shelters/{id}/contacts` | Контакти коменданта (CONFIDENTIAL) | `DSNS_OPERATOR`; `SHELTER_MANAGER` — лише своє укриття |
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

Коди `error` для відмов збігаються з типами подій у журналі аудиту.
Для порушень правил якості даних (SG-21) зарезервовано `422` з окремим кодом; його назву треба
узгодити в команді — зараз у документах трапляються три варіанти.

## Згода

Цілі: `ROUTE_GPS` (маршрут і пошук найближчого укриття), `REPORT_GEOFENCE` (перевірка присутності
біля укриття для звіту), `SOS`. Стани: `NOT_GRANTED`, `ACTIVE`, `REVOKED`, `EXPIRED`.

- Згода гранулярна: дозвіл на одну ціль не поширюється на інші.
- `POST /consents` повертає `201`, якщо згоду створено, і `200`, якщо вона вже була активна.
- Відкликання діє одразу: наступний запит, що потребує цієї згоди, отримає `403`.
- Записи не видаляються: відкликання ставить дату, повторна згода створює новий запис.
- Відмова від згоди не обмежує перегляд публічної мапи.

## Що записується в журнал аудиту

| Подія | Результат |
|---|---|
| `DENIED_401_AUTH`, `DENIED_403_RBAC`, `DENIED_403_CONSENT` | DENIED |
| `USER_REGISTERED`, `LOGIN_SUCCESS` | SUCCESS |
| `CONSENT_GRANTED`, `CONSENT_REVOKED` | SUCCESS |
| `SHELTER_READ_CONTACTS`, `SHELTER_NEARBY_SEARCH` | SUCCESS |

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

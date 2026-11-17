"""Перевірка, що прототип SkyGuard піднявся повністю (SG-24).

Запускати після `docker compose up -d --build --wait`:

    python scripts/check_stack.py

Потрібен лише Python 3.10+ без жодних пакетів. Скрипт перевіряє БД і API,
фронтенд, CORS між ними, вхід кожного тестового користувача та цілісність
журналу аудиту. Код виходу 0 — усе працює, 1 — є проблема (див. підказку).
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

PASSWORD = "skyguard-demo"
USERS = [
    ("citizen@skyguard.demo", "CITIZEN"),
    ("volunteer@skyguard.demo", "VERIFIED_VOLUNTEER"),
    ("manager@skyguard.demo", "SHELTER_MANAGER"),
    ("dsns@skyguard.demo", "DSNS_OPERATOR"),
    ("auditor@skyguard.demo", "SECURITY_AUDITOR"),
]


def call(method, url, body=None, headers=None):
    """Повертає (статус, заголовки, тіло). Мережева помилка — статус None."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        return None, {}, str(getattr(exc, "reason", exc))


class Report:
    def __init__(self):
        self.failed = 0

    def ok(self, text):
        print(f"  [OK]   {text}")

    def fail(self, text, hint):
        self.failed += 1
        print(f"  [FAIL] {text}\n         → {hint}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--front", default="http://localhost:8085")
    args = ap.parse_args()
    api, front = args.api.rstrip("/"), args.front.rstrip("/")
    r = Report()

    print(f"SkyGuard: перевірка {api} і {front}\n")

    # 1. API і БД
    status, _, body = call("GET", f"{api}/health/ready")
    if status == 200 and '"up"' in body:
        r.ok("API працює, PostgreSQL доступна (/health/ready)")
    elif status is None:
        r.fail(
            f"API не відповідає: {body}",
            "docker compose ps — чи запущений сервіс api? Логи: docker compose logs api",
        )
        print("\nДалі перевіряти немає сенсу, поки API не запущено.")
        return 1
    else:
        r.fail(f"/health/ready → {status} {body[:120]}", "docker compose logs db api")

    # 2. Демо-дані
    status, _, body = call("GET", f"{api}/api/v1/shelters")
    try:
        count = len(json.loads(body).get("features", [])) if status == 200 else 0
    except ValueError:
        count = 0
    if count:
        r.ok(f"Реєстр укриттів: {count} укриттів у БД")
    else:
        r.fail(
            f"/api/v1/shelters → {status}, укриттів: {count}",
            "засів не відбувся: docker compose logs api (шукайте app.seed)",
        )

    # 3. Фронтенд
    status, _, body = call("GET", f"{front}/")
    if status == 200 and "SkyGuard" in body:
        r.ok("Веб-інтерфейс віддається (nginx)")
    else:
        r.fail(
            f"{front}/ → {status}",
            "docker compose ps — чи запущений сервіс frontend? Чи вільний порт 8085?",
        )

    # 4. CORS: браузер на 8085 має право звертатися до API на 8000
    status, headers, _ = call(
        "OPTIONS",
        f"{api}/api/v1/auth/login",
        headers={
            "Origin": front,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    allowed = headers.get("access-control-allow-origin") if headers else None
    if status == 200 and allowed in (front, "*"):
        r.ok(f"CORS дозволяє запити з {front}")
    else:
        r.fail(
            f"CORS не дозволяє {front} (статус {status}, allow-origin={allowed})",
            "у .env рядок CORS_ORIGINS має містити цю адресу; найпростіше — видаліть "
            ".env або скопіюйте .env.example наново, потім docker compose up -d",
        )

    # 5. Тестові користувачі
    tokens = {}
    for email, role in USERS:
        status, _, body = call(
            "POST", f"{api}/api/v1/auth/login", {"email": email, "password": PASSWORD}
        )
        data = json.loads(body) if status == 200 else {}
        if status == 200 and data.get("role") == role:
            tokens[role] = data["access_token"]
            r.ok(f"Вхід {email} → {role}")
        else:
            r.fail(
                f"Вхід {email} → {status} {body[:100]}",
                "демо-користувачі створюються засівом при старті API: docker compose logs api",
            )

    # 6. Журнал аудиту цілісний (лише аудитор має доступ)
    if "SECURITY_AUDITOR" in tokens:
        status, _, body = call(
            "GET",
            f"{api}/api/v1/governance/audit-trail?limit=5",
            headers={"Authorization": f"Bearer {tokens['SECURITY_AUDITOR']}"},
        )
        verified = json.loads(body).get("integrity_verified") if status == 200 else None
        if verified is True:
            r.ok("Журнал аудиту: ланцюжок SHA-256 цілісний (integrity_verified)")
        else:
            r.fail(
                f"audit-trail → {status}, integrity_verified={verified}",
                "журнал пошкоджено або міграції не застосовано: docker compose logs api",
            )

    print()
    if r.failed:
        print(f"Проблем: {r.failed}. Див. розділ «Якщо щось не працює» у README.md")
        return 1
    print(f"Усе працює. Відкрийте {front}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

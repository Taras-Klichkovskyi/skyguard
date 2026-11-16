"""SG-11 / TC-06: Читання незмінного журналу аудиту (Audit Trail).

Критерії:
  - Лише SECURITY_AUDITOR може читати журнал (200 OK, integrity_verified=True).
  - CITIZEN (та інші неаудитори) отримують 403 DENIED_403_RBAC із записом у журналі.
  - Без токена повертається 401 DENIED_401_AUTH.
"""

from app.models.enums import RoleCode

AUDIT_URL = "/api/v1/governance/audit-trail"


def test_tc06_unauthenticated_reading_audit_trail_is_401(client):
    """TC-06 (частина 1): запит без токена повертає 401."""
    r = client.get(AUDIT_URL)
    assert r.status_code == 401
    assert r.json()["error"] == "DENIED_401_AUTH"
    assert "audit_entry_id" in r.json()


def test_tc06_citizen_reading_audit_trail_is_forbidden(client, make_user, auth):
    """TC-06 (частина 2): Citizen з валідним токеном отримує 403 DENIED_403_RBAC."""
    citizen = make_user(RoleCode.CITIZEN)
    headers = auth(citizen)

    r = client.get(AUDIT_URL, headers=headers)
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "DENIED_403_RBAC"
    assert body["role"] == "CITIZEN"
    assert "audit_entry_id" in body


def test_tc06_auditor_reading_audit_trail_is_200_and_integrity_verified(client, make_user, auth):
    """TC-06 (частина 3): Security Auditor успішно читає зріз журналу з перевіркою хеш-ланцюга."""
    auditor = make_user(RoleCode.SECURITY_AUDITOR)
    headers = auth(auditor)

    r = client.get(AUDIT_URL, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["integrity_verified"] is True
    assert "audit_event_id" in body
    assert "entries" in body
    assert isinstance(body["entries"], list)


def test_tc06_tampered_record_is_detected_by_the_endpoint(client, make_user, auth, db):
    """Підміна вмісту запису ламає перевірку, навіть якщо зв'язки prev_hash цілі."""
    from sqlalchemy import text

    auditor = make_user(RoleCode.SECURITY_AUDITOR)
    headers = auth(auditor)
    assert client.get(AUDIT_URL, headers=headers).json()["integrity_verified"] is True

    # Зловмисник із правами суперкористувача БД обходить тригер і змінює дію в записі
    db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_modify"))
    db.execute(
        text("UPDATE audit_log SET action = 'TAMPERED' WHERE id = (SELECT min(id) FROM audit_log)")
    )
    db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_modify"))

    assert client.get(AUDIT_URL, headers=headers).json()["integrity_verified"] is False

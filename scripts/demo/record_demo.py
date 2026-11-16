"""Запис кадрів демонстраційного відео SG-17 (сценарій A — 7 кроків, сценарій B — 403).

Скрипт проходить демо-сценарій у справжньому браузері проти запущеного прототипу
й зберігає кадри (JPEG) та журнал справжніх запитів і відповідей API. З цих
матеріалів монтується відео (scripts/demo/compose_video.py).

Підготовка (один раз):
    python -m pip install playwright
    python -m playwright install chromium

Запуск — лише на ЧИСТІЙ базі, інакше консоль аудитора покаже старі записи:
    docker compose down -v
    docker compose up -d --build
    python scripts/demo/record_demo.py

Результат: demo_capture.zip у поточній папці.
Параметри: --front http://localhost:8085/  --api http://localhost:8000/api/v1
           --out demo_capture  --headed (показати вікна браузера)
           --leaflet-dir DIR (локальна копія leaflet/dist, якщо unpkg недоступний)
"""

import argparse
import asyncio
import contextlib
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

RYNOK = {"latitude": 49.8419, "longitude": 24.0315}  # пл. Ринок, ~470 м від укриття
AT_ENTRANCE = {"latitude": 49.84020, "longitude": 24.03730}  # ~35 м від входу
SHELTER_NAME = "Митна"  # DEMO-0006 «Підземний перехід, пл. Митна»
VIEWPORT = {"width": 1440, "height": 900}


class Recorder:
    def __init__(self, out: Path, api: str, leaflet_dir: str | None = None):
        self.out = out
        self.api = api
        self.leaflet_dir = leaflet_dir
        self.frames_dir = out / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.t0 = time.monotonic()
        self.shots: list[dict] = []
        self.events: list[dict] = []
        self._sent = 0  # events already attached to a shot

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 3)

    # ---------- network log ----------

    def attach(self, page, actor: str) -> None:
        async def on_response(resp):
            if "/api/v1/" not in resp.url:
                return
            req = resp.request
            try:
                body = await resp.json()
            except Exception:
                body = None
            self.events.append(
                {
                    "t": self.now(),
                    "actor": actor,
                    "kind": "http",
                    "method": req.method,
                    "path": "/api/v1/" + resp.url.split("/api/v1/", 1)[1],
                    "status": resp.status,
                    "req": sanitize(_json(req.post_data)),
                    "res": summarize(sanitize(body)),
                }
            )

        def on_ws(ws):
            def frame(payload):
                msg = _json(payload)
                if isinstance(msg, dict) and msg.get("type") == "shelter.updated":
                    self.events.append(
                        {
                            "t": self.now(),
                            "actor": actor,
                            "kind": "ws",
                            "method": "WS",
                            "path": "/ws/v1/shelters",
                            "status": None,
                            "req": None,
                            "res": summarize(msg),
                        }
                    )

            ws.on("framereceived", frame)

        page.on("response", on_response)
        page.on("websocket", on_ws)

    # ---------- frames ----------

    async def shot(self, page, actor, step, name, *, burst=1, gap_ms=140, hold=None):
        """Знімає кадр (або серію кадрів) і прив'язує до нього нові події API."""
        for i in range(burst):
            idx = len(self.shots)
            file = f"{idx:03d}_{actor}_{name}{'' if burst == 1 else f'_{i}'}.jpg"
            await page.screenshot(path=str(self.frames_dir / file), type="jpeg", quality=92)
            new = list(range(self._sent, len(self.events)))
            self._sent = len(self.events)
            self.shots.append(
                {
                    "file": file,
                    "actor": actor,
                    "step": step,
                    "name": name,
                    "t": self.now(),
                    "click": None,  # див. mark_click
                    "events": new,
                    "hold": hold,
                }
            )
            if i < burst - 1:
                await page.wait_for_timeout(gap_ms)

    def mark_click(self, actor: str, point: dict) -> None:
        """Позначає клік на останньому кадрі цього актора, знятому ДО кліку."""
        for shot in reversed(self.shots):
            if shot["actor"] == actor:
                shot["click"] = point
                return

    def save(self) -> Path:
        meta = {"viewport": VIEWPORT, "shots": self.shots, "events": self.events}
        (self.out / "capture.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        archive = shutil.make_archive(str(self.out), "zip", root_dir=self.out)
        return Path(archive)


# ---------- helpers ----------


def _json(raw):
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def sanitize(obj):
    """Паролі та токени не потрапляють у кадр і в архів."""
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if k == "password":
                clean[k] = "••••••"
            elif k in ("access_token", "refresh_token") and isinstance(v, str):
                clean[k] = v[:10] + "…"
            else:
                clean[k] = sanitize(v)
        return clean
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj


def summarize(body):
    """Великі відповіді стискаються до того, що варто показати в кадрі."""
    if not isinstance(body, dict):
        return body
    if body.get("type") == "FeatureCollection":
        return {"type": "FeatureCollection", "features": len(body.get("features", []))}
    if "entries" in body:
        entries = body.get("entries") or []
        return {
            "integrity_verified": body.get("integrity_verified"),
            "count": body.get("count"),
            "last": [
                {k: e.get(k) for k in ("id", "actor_role", "action", "http_status")}
                for e in entries[-4:]
            ],
        }
    if body.get("type") == "shelter.updated":
        props = (body.get("shelter") or {}).get("properties", {})
        return {
            "type": "shelter.updated",
            "source": body.get("source"),
            "shelter": props.get("name"),
            "status": props.get("status"),
        }
    if "shelter" in body and isinstance(body["shelter"], dict):
        props = body["shelter"].get("properties", {})
        body = {**body, "shelter": {"name": props.get("name"), "status": props.get("status")}}
    return body


async def new_actor(browser, rec, actor, geo):
    ctx = await browser.new_context(
        viewport=VIEWPORT,
        geolocation=geo,
        permissions=["geolocation"],
        locale="uk-UA",
        device_scale_factor=1,
    )
    page = await ctx.new_page()
    if rec.leaflet_dir:
        dist = Path(rec.leaflet_dir)

        async def leaflet(route):
            name = route.request.url.split("/dist/")[-1].split("?")[0]
            await route.fulfill(path=str(dist / name))

        await page.route("https://unpkg.com/leaflet@1.9.4/dist/**", leaflet)
    rec.attach(page, actor)
    return ctx, page


async def open_app(page, front):
    await page.goto(front, wait_until="load")
    await page.wait_for_function(
        "() => window.SkyGuard && SkyGuard.State.shelters.length > 0 && "
        "SkyGuard.State.shelters.some(s => /^[0-9a-f-]{36}$/.test(String(s.id)))",
        timeout=20000,
    )
    await settle(page)


async def settle(page, ms=1200):
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("networkidle", timeout=4000)
    await page.wait_for_timeout(ms)


async def dismiss_consent_prompt(page):
    """Закриває вікно згоди хрестиком: без рішення і без запитів до сервера."""
    try:
        await page.wait_for_selector("#consentModal.active", timeout=4000)
        await page.click("#closeConsentModalBtn")
        await page.wait_for_timeout(300)
    except Exception:
        pass


async def switch_role(page, role):
    await page.click("#btnOpenAuthModal")
    await page.wait_for_timeout(300)
    await page.click(f".role-select-card[data-role={role}] .btn-switch-role")
    await page.wait_for_timeout(300)
    if await page.is_visible("#btnConfirmRolePass"):
        await page.click("#btnConfirmRolePass")
    await page.wait_for_timeout(1500)


async def scroll_audit_to_end(page):
    """Прокручує таблицю журналу до найсвіжіших записів."""
    await page.evaluate(
        """() => {
          let el = document.querySelector('#auditTable');
          while (el && el.scrollHeight <= el.clientHeight) el = el.parentElement;
          if (el) el.scrollTop = el.scrollHeight;
        }"""
    )


async def scroll_audit_to(page, action):
    """Прокручує таблицю журналу так, щоб перший рядок із цією дією був угорі."""
    await page.evaluate(
        """(action) => {
          let el = document.querySelector('#auditTable');
          while (el && el.scrollHeight <= el.clientHeight) el = el.parentElement;
          const row = Array.from(document.querySelectorAll('#auditTableBody tr'))
            .find(r => r.innerText.includes(action));
          const head = document.querySelector('#auditTable thead');
          if (el && row) el.scrollTop = row.offsetTop - (head ? head.offsetHeight : 0);
        }""",
        action,
    )


async def center_of(page, selector):
    box = await page.locator(selector).first.bounding_box()
    return {"x": round(box["x"] + box["width"] / 2), "y": round(box["y"] + box["height"] / 2)}


async def marker_point(page, shelter_id):
    return await page.evaluate(
        """(id) => {
          const s = SkyGuard.State.getShelterById(id);
          const m = SkyGuard.Map.instance;
          const p = m.latLngToContainerPoint([s.lat, s.lon]);
          const r = m.getContainer().getBoundingClientRect();
          return {x: Math.round(r.left + p.x), y: Math.round(r.top + p.y)};
        }""",
        shelter_id,
    )


async def press(rec, page, actor, selector):
    """Клік із позначкою для відео: кружечок з'явиться на кадрі перед дією."""
    rec.mark_click(actor, await center_of(page, selector))
    await page.click(selector)


async def submit_report(page, status="CLOSED"):
    await page.click("#openReportBtn")
    await page.wait_for_selector("#reportModal.active")
    await page.check(f"input[name=reportStatus][value={status}]")
    await page.wait_for_timeout(250)


def preflight(front, api):
    try:
        ready = json.load(
            urllib.request.urlopen(api.rsplit("/api/v1", 1)[0] + "/health/ready", timeout=5)
        )
        assert ready.get("database") == "up"
        shelters = json.load(urllib.request.urlopen(api + "/shelters", timeout=5))["features"]
        urllib.request.urlopen(front, timeout=5)
    except Exception as exc:
        sys.exit(f"Прототип не відповідає ({exc}). Запустіть: docker compose up -d --build")
    target = [f for f in shelters if SHELTER_NAME in f["properties"]["name"]]
    if not target:
        sys.exit(
            "Укриття «пл. Митна» немає в базі. Запустіть з чистої бази: docker compose down -v"
        )
    if target[0]["properties"]["status"] != "OPEN":
        sys.exit(
            "Укриття «пл. Митна» вже не OPEN — схоже, сценарій уже проганяли.\n"
            "Почніть з чистої бази: docker compose down -v && docker compose up -d --build"
        )


# ---------- scenario ----------


async def run(front, api, out, headed, leaflet_dir=None):
    preflight(front, api)
    rec = Recorder(out, api, leaflet_dir)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)

        # ===== 1. ЗАПИТ: публічний реєстр укриттів =====
        c_ctx, c = await new_actor(browser, rec, "citizen", RYNOK)
        await open_app(c, front)
        await dismiss_consent_prompt(c)
        sid = await c.evaluate(
            f"SkyGuard.State.shelters.find(s => s.name.includes('{SHELTER_NAME}')).id"
        )
        await settle(c, 800)
        await rec.shot(c, "citizen", 1, "registry", hold=4.5)
        rec.mark_click("citizen", await marker_point(c, sid))
        await c.evaluate(f"SkyGuard.UI.openShelterDetails('{sid}')")
        await c.wait_for_timeout(700)
        await rec.shot(c, "citizen", 1, "public_card", hold=4.5)

        # ===== 2. ПРАВО: JWT і роль =====
        await press(rec, c, "citizen", "#btnOpenAuthModal")
        await c.wait_for_timeout(500)
        await rec.shot(c, "citizen", 2, "roles", hold=4.0)
        await press(rec, c, "citizen", ".role-select-card[data-role=CITIZEN] .btn-switch-role")
        await c.wait_for_timeout(900)
        await rec.shot(c, "citizen", 2, "jwt", hold=4.5)

        # ===== 3. ЗГОДА: гранулярна згода на GPS =====
        await c.evaluate("SkyGuard.Security.openConsentModal()")
        await c.wait_for_timeout(500)
        await rec.shot(c, "citizen", 3, "consent_modal", hold=4.0)
        await press(rec, c, "citizen", "#btnGrantConsent")
        await c.wait_for_timeout(1200)
        await rec.shot(c, "citizen", 3, "consent_granted", burst=2, gap_ms=350, hold=2.6)
        await settle(c, 600)
        await c.evaluate(f"SkyGuard.UI.openShelterDetails('{sid}')")
        await c.wait_for_timeout(500)
        await rec.shot(c, "citizen", 3, "route", hold=3.5)

        # ===== 4. ЯКІСТЬ: DQ-1 (422), потім звіт біля входу (кворум 1/3) =====
        await submit_report(c)
        await rec.shot(c, "citizen", 4, "report_far", hold=4.0)
        await press(rec, c, "citizen", "#btnSubmitReport")
        await c.wait_for_timeout(700)
        await rec.shot(c, "citizen", 4, "dq1_422", hold=5.0)

        await c_ctx.set_geolocation(AT_ENTRANCE)
        await press(rec, c, "citizen", "#consentBtn")
        await c.wait_for_timeout(1500)
        await c.evaluate(f"SkyGuard.UI.openShelterDetails('{sid}')")
        await settle(c, 500)
        await rec.shot(c, "citizen", 4, "at_entrance", hold=3.5)
        await submit_report(c)
        await rec.shot(c, "citizen", 4, "report_near", hold=3.5)
        await press(rec, c, "citizen", "#btnSubmitReport")
        await c.wait_for_timeout(700)
        await rec.shot(c, "citizen", 4, "quorum_1of3", hold=5.0)

        # ----- за кадром: волонтер і диспетчер ДСНС готуються -----
        v_ctx, v = await new_actor(browser, rec, "volunteer", AT_ENTRANCE)
        await open_app(v, front)
        await dismiss_consent_prompt(v)
        await switch_role(v, "VOLUNTEER")
        await v.evaluate("SkyGuard.Security.openConsentModal()")
        await v.wait_for_timeout(300)
        await v.click("#btnGrantConsent")
        await v.wait_for_timeout(1800)
        await v.evaluate(f"SkyGuard.UI.openShelterDetails('{sid}')")
        await settle(v, 500)

        d_ctx, d = await new_actor(browser, rec, "dsns", RYNOK)
        await open_app(d, front)
        await dismiss_consent_prompt(d)
        await switch_role(d, "OPERATOR")
        await d.evaluate(
            f"""(() => {{ const s = SkyGuard.State.getShelterById('{sid}');
                 SkyGuard.Map.instance.setView([s.lat, s.lon], 15.5);
                 SkyGuard.UI.openShelterDetails('{sid}'); }})()"""
        )
        await settle(d, 900)
        rec._sent = len(rec.events)  # підготовчі запити в кадр не йдуть

        # ===== 5. ПЕРЕДАЧА: волонтер добирає кворум, статус застосовано =====
        await rec.shot(v, "volunteer", 5, "volunteer_ready", hold=3.5)
        await rec.shot(d, "dsns", 6, "dispatcher_before", hold=3.5)
        await submit_report(v)
        await rec.shot(v, "volunteer", 5, "volunteer_report", hold=3.0)
        await press(rec, v, "volunteer", "#btnSubmitReport")
        await v.wait_for_timeout(600)
        await rec.shot(v, "volunteer", 5, "quorum_reached", hold=5.0)

        # ===== 6. СПОВІЩЕННЯ: інший клієнт отримує shelter.updated =====
        await d.wait_for_timeout(300)
        await rec.shot(d, "dsns", 6, "dispatcher_after", burst=2, gap_ms=400, hold=3.0)

        # ===== 7. ФІКСАЦІЯ: журнал аудиту =====
        a_ctx, a = await new_actor(browser, rec, "auditor", RYNOK)
        await open_app(a, front)
        await dismiss_consent_prompt(a)
        rec._sent = len(rec.events)
        await switch_role(a, "AUDITOR")
        await a.wait_for_selector("#auditModal.active", timeout=8000)
        await a.wait_for_timeout(2500)
        await scroll_audit_to(a, "CONSENT_GRANTED")
        await a.wait_for_timeout(400)
        await rec.shot(a, "auditor", 7, "audit_quality", hold=6.0)
        await scroll_audit_to(a, "UPDATE_STATUS_VERIFIED")
        await a.wait_for_timeout(400)
        await rec.shot(a, "auditor", 7, "audit_transfer", hold=5.0)

        # ===== B. Відмова 403 і запис в аудиті =====
        await c.evaluate(f"SkyGuard.UI.openShelterDetails('{sid}')")
        await c.wait_for_timeout(400)
        await c.locator("#requestTelemetryBtn").scroll_into_view_if_needed()
        await c.wait_for_timeout(400)
        await rec.shot(c, "citizen", "B", "contacts_button", hold=3.5)
        await press(rec, c, "citizen", "#requestTelemetryBtn")
        await c.wait_for_selector("#forbiddenModal.active", timeout=8000)
        await c.wait_for_timeout(500)
        await rec.shot(c, "citizen", "B", "forbidden_403", hold=7.0)

        await a.wait_for_timeout(3200)  # консоль аудитора оновлюється кожні 2,5 с
        await press(rec, a, "auditor", "#auditFilter403")
        await a.wait_for_timeout(600)
        await scroll_audit_to_end(a)
        await rec.shot(a, "auditor", "B", "audit_403", hold=7.0)

        await browser.close()

    archive = rec.save()
    print(f"Готово: {len(rec.shots)} кадрів, {len(rec.events)} подій API -> {archive}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--front", default="http://localhost:8085/")
    ap.add_argument("--api", default="http://localhost:8000/api/v1")
    ap.add_argument("--out", default="demo_capture")
    ap.add_argument("--headed", action="store_true", help="показати вікна браузера")
    ap.add_argument("--leaflet-dir", help="локальна копія leaflet/dist, якщо unpkg недоступний")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    asyncio.run(run(args.front, args.api.rstrip("/"), out, args.headed, args.leaflet_dir))


if __name__ == "__main__":
    main()

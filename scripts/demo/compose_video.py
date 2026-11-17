"""Монтаж демонстраційного відео SG-17 з кадрів, знятих record_demo.py.

    python scripts/demo/compose_video.py demo_capture.zip -o SkyGuard_demo_SG-17.mp4

Кожен кадр розміщується в рамці 1920×1080:
  * угорі — номер і назва кроку та ланцюжок «запит → … → фіксація»;
  * ліворуч — знімок прототипу 1440×900;
  * праворуч — справжні запити й відповіді API, записані під час зйомки;
  * унизу — підпис, що відбувається.
Потрібні Pillow і ffmpeg.
"""

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
TOP, BOTTOM = 96, 84
SHOT_W, SHOT_H = 1440, 900
PANEL_X = SHOT_W
FPS = 30
PACE = 1.15  # множник тривалості кадрів

FONT_DIR = Path("/usr/share/fonts/opentype/inter")
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

BG = (8, 12, 22)
PANEL = (15, 21, 34)
CARD = (22, 30, 46)
LINE = (44, 56, 78)
TEXT = (231, 236, 245)
MUTED = (148, 160, 182)
DIM = (96, 108, 130)
BLUE = (59, 130, 246)
GREEN = (16, 185, 129)
RED = (239, 68, 68)
AMBER = (245, 158, 11)
VIOLET = (139, 92, 246)

CHAIN = ["Запит", "Право", "Згода", "Якість", "Передача", "Сповіщення", "Фіксація"]
STEP_TITLES = {
    1: "Запит — публічний реєстр укриттів",
    2: "Право — автентифікація JWT і роль",
    3: "Згода — гранулярна згода на GPS",
    4: "Якість — правила DQ-1 і DQ-3",
    5: "Передача — кворум зібрано, статус застосовано",
    6: "Сповіщення — WebSocket-пуш іншим клієнтам",
    7: "Фіксація — незмінний журнал аудиту",
    "B": "Відмова 403 і запис в аудиті",
}
ACTORS = {
    "citizen": ("Мешканка", "citizen@skyguard.demo"),
    "volunteer": ("Волонтер", "volunteer@skyguard.demo"),
    "dsns": ("Диспетчер ДСНС", "dsns@skyguard.demo"),
    "auditor": ("Аудитор безпеки", "auditor@skyguard.demo"),
}
CAPTIONS = {
    "registry": "Мапа завантажує публічний реєстр: 8 укриттів Львова у форматі GeoJSON, без токена й без згоди.",
    "public_card": "Картка укриття відкрита всім. Відстань прихована: без згоди координати користувача не обробляються.",
    "roles": "Шість ролей RBAC за політикою Data Governance. Права визначає роль, а не інтерфейс.",
    "jwt": "Сервер видає JWT на 15 хв із роллю CITIZEN. Далі кожен запит несе цей токен.",
    "consent_modal": "Згода за ст. 11 ЗУ «Про захист персональних даних»: окремо для маршруту і для звітів.",
    "consent_granted": "Сервер записує дві згоди (201 Created) — ROUTE_GPS і REPORT_GEOFENCE.",
    "route": "Лише тепер GPS використовується: найближче відчинене укриття — 472 м, маршрут пішки.",
    "report_far": "Мешканка повідомляє, що укриття зачинене, стоячи на площі Ринок — за 472 м від входу.",
    "dq1_422": "DQ-1: сервер сам рахує відстань за Haversine. 472 м > 100 м → 422, звіт відхилено й записано в аудит.",
    "at_entrance": "Мешканка підходить до входу: 33 м від укриття.",
    "report_near": "Той самий звіт з відстані 33 м проходить DQ-1.",
    "quorum_1of3": "DQ-3: один звіт мешканця має вагу 1 з 3. Статус ще не змінено — «потребує підтвердження».",
    "volunteer_ready": "Інший користувач — верифікований волонтер (вага звіту 3) — теж біля входу.",
    "volunteer_report": "Волонтер підтверджує: укриття зачинене.",
    "quorum_reached": "Кворум зібрано (1 + 3 ≥ 3): статус «зачинено» застосовано в базі даних.",
    "dispatcher_before": "Тим часом диспетчер ДСНС дивиться на те саме укриття: воно ще «відчинено».",
    "dispatcher_after": "Без оновлення сторінки: сервер надіслав shelter.updated, маркер став червоним.",
    "audit_quality": "Аудитор бачить кожен крок: згоди, відхилений звіт (422), звіт у очікуванні кворуму.",
    "audit_transfer": "І застосування статусу. Сервер перерахував ланцюжок SHA-256: integrity_verified = true.",
    "contacts_button": "Мешканка пробує відкрити службові контакти коменданта — дані класу CONFIDENTIAL.",
    "forbidden_403": "Сервер відмовляє: 403 DENIED_403_RBAC. У відповіді — номер запису аудиту.",
    "audit_403": "Аудитор фільтрує відмови: той самий запис, зроблений до відповіді клієнту.",
}
STEP_ORDER = [1, 2, 3, 4, 5, 6, 7, "B"]
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def font(weight="Regular", size=24):
    path = FONT_DIR / f"Inter-{weight}.otf"
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)


def mono(size=17, bold=False):
    return ImageFont.truetype(MONO_B if bold else MONO, size)


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ---------- API panel ----------


def describe(e):
    """Що показати про подію API: (заголовок, колір, рядки)."""
    res = e.get("res") if isinstance(e.get("res"), dict) else {}
    path = UUID.sub("{id}", e["path"]).split("?")[0]
    if e["kind"] == "ws":
        return (
            "WS  shelter.updated",
            VIOLET,
            [
                f"source: {res.get('source')}",
                f"{res.get('shelter')}",
                f"status → {res.get('status')}",
            ],
        )
    status = e["status"]
    color = GREEN if status and status < 300 else AMBER if status in (401, 429) else RED
    head = f"{e['method']} {path}"
    lines = []
    if path.endswith("/shelters") and res.get("type") == "FeatureCollection":
        lines = [f"FeatureCollection · {res.get('features')} укриттів", "без токена (дані PUBLIC)"]
    elif path.endswith("/auth/login"):
        lines = [
            f"role: {res.get('role')}",
            f"access_token: {res.get('access_token')}",
            f"expires_in: {res.get('expires_in')} с",
        ]
    elif path.endswith("/consents"):
        lines = [
            f"purpose: {res.get('purpose')}",
            f"status: {res.get('status')} · policy {res.get('policy_version')}",
        ]
    elif path.endswith("/reports") or path.endswith("/status"):
        if status == 200:
            q = res.get("quorum") or {}
            lines = [
                f"applied: {str(res.get('applied')).lower()}",
                f"validation: {res.get('validation_status')}",
                f"quorum: {q.get('collected')}/{q.get('required')} · {res.get('distance_m')} м",
            ]
            if res.get("applied"):
                lines.append(f"status → {(res.get('shelter') or {}).get('status')}")
        else:
            lines = [
                f"error: {res.get('error')}",
                f"rule: {res.get('rule')} · {res.get('distance_m')} м > {res.get('max_distance_m')} м",
                f"audit_entry_id: #{res.get('audit_entry_id')}",
            ]
    elif path.endswith("/contacts"):
        if status == 403:
            lines = [
                f"error: {res.get('error')}",
                f"role: {res.get('role')} · {res.get('data_classification')}",
                f"required: {', '.join(res.get('required_roles') or [])}",
                f"audit_entry_id: #{res.get('audit_entry_id')}",
            ]
        else:
            lines = [f"{res.get('commander_name')}", f"{res.get('commander_phone')}"]
    elif "/governance/audit-trail" in path:
        lines = [
            f"integrity_verified: {str(res.get('integrity_verified')).lower()}",
            f"записів у зрізі: {res.get('count')}",
        ]
    return f"{head}  {status}", color, lines


def relevant(events, shot, prev_t):
    """Події вікна цього актора між попереднім і поточним кадром (без шуму)."""
    picked = []
    for e in events:
        if e["actor"] != shot["actor"] or not (prev_t < e["t"] <= shot["t"]):
            continue
        if e["path"].endswith("/consents") and e["status"] == 200:
            continue  # повторна синхронізація вже наданої згоди
        if e["kind"] == "ws" and shot["step"] != 6:
            continue  # сповіщення показуємо в кроці 6
        res = e.get("res") if isinstance(e.get("res"), dict) else {}
        if (
            shot["actor"] != "citizen"
            and e["path"].endswith("/auth/login")
            and res.get("role") == "CITIZEN"
        ):
            continue  # фронтенд при відкритті входить гостем-мешканцем, до вибору ролі
        picked.append(e)
    # консоль аудитора опитує журнал кожні 2,5 с: показуємо лише останнє опитування
    reads = [e for e in picked if "/governance/audit-trail" in e["path"]]
    if len(reads) > 1:
        picked = [e for e in picked if e not in reads[:-1]]
    return picked


def draw_panel(img, cards):
    d = ImageDraw.Draw(img)
    x0, y0 = PANEL_X, TOP
    d.rectangle([x0, y0, W, H - BOTTOM], fill=PANEL)
    d.line([x0, y0, x0, H - BOTTOM], fill=LINE, width=2)
    d.text((x0 + 24, y0 + 20), "API · відповіді сервера", font=font("SemiBold", 22), fill=TEXT)
    d.text((x0 + 24, y0 + 50), "записано під час зйомки", font=font("Regular", 16), fill=DIM)
    y = y0 + 88
    for head, color, lines, fresh in cards:
        h = 44 + 24 * len(lines)
        if y + h > H - BOTTOM - 12:
            break
        d.rounded_rectangle(
            [x0 + 16, y, W - 16, y + h],
            radius=10,
            fill=CARD,
            outline=color if fresh else LINE,
            width=2 if fresh else 1,
        )
        d.rectangle([x0 + 16, y + 8, x0 + 20, y + h - 8], fill=color)
        d.text((x0 + 32, y + 12), head, font=mono(16, bold=True), fill=color)
        for j, line in enumerate(lines):
            d.text(
                (x0 + 32, y + 40 + 24 * j), line[:44], font=mono(15), fill=TEXT if fresh else MUTED
            )
        y += h + 12


# ---------- frame ----------


def draw_header(img, step):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, TOP], fill=BG)
    d.line([0, TOP - 1, W, TOP - 1], fill=LINE, width=2)
    if step == "B":
        badge, color = "СЦЕНАРІЙ B", RED
    else:
        badge, color = f"КРОК {step} / 7", BLUE
    bw = d.textlength(badge, font=font("Bold", 20)) + 32
    d.rounded_rectangle([28, 28, 28 + bw, 68], radius=20, fill=color)
    d.text((44, 36), badge, font=font("Bold", 20), fill=(255, 255, 255))
    d.text((48 + bw, 30), STEP_TITLES[step], font=font("SemiBold", 30), fill=TEXT)
    # ланцюжок
    x = W - 28
    f = font("Medium", 17)
    for i in range(len(CHAIN) - 1, -1, -1):
        label = CHAIN[i]
        tw = d.textlength(label, font=f)
        x -= tw
        n = i + 1
        active = step == n
        done = step != "B" and n < step
        fill = TEXT if active else (MUTED if done else DIM)
        if active:
            d.rounded_rectangle([x - 10, 30, x + tw + 10, 66], radius=18, fill=(30, 58, 110))
        d.text((x, 38), label, font=f, fill=fill)
        if i:
            x -= 44
            d.text((x + 12, 38), "→", font=f, fill=DIM)
        x -= 4


def draw_caption(img, text, actor):
    d = ImageDraw.Draw(img)
    y0 = H - BOTTOM
    d.rectangle([0, y0, W, H], fill=BG)
    d.line([0, y0, W, y0], fill=LINE, width=2)
    who, email = ACTORS[actor]
    d.text((28, y0 + 16), who, font=font("Bold", 18), fill=AMBER)
    d.text((28, y0 + 44), email, font=font("Regular", 14), fill=DIM)
    lines = wrap(d, text, font("Medium", 25), W - 300)
    ty = y0 + (BOTTOM - 32 * len(lines)) / 2 + 2
    for line in lines[:2]:
        d.text((260, ty), line, font=font("Medium", 25), fill=TEXT)
        ty += 32


def draw_click(img, point):
    d = ImageDraw.Draw(img, "RGBA")
    x, y = point["x"], point["y"] + TOP
    for r, a in ((34, 70), (26, 120)):
        d.ellipse([x - r, y - r, x + r, y + r], outline=(245, 158, 11, a + 80), width=4)
    d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(245, 158, 11, 230))


def compose_shot(frames_dir, shot, cards, with_click):
    img = Image.new("RGB", (W, H), BG)
    shot_img = Image.open(frames_dir / shot["file"]).convert("RGB")
    if shot_img.size != (SHOT_W, SHOT_H):
        shot_img = shot_img.resize((SHOT_W, SHOT_H), Image.LANCZOS)
    img.paste(shot_img, (0, TOP))
    if with_click and shot.get("click"):
        draw_click(img, shot["click"])
    draw_header(img, shot["step"])
    draw_panel(img, cards)
    draw_caption(img, CAPTIONS.get(shot["name"], ""), shot["actor"])
    return img


# ---------- cards ----------


def title_card(title, subtitle, lines, accent=BLUE, chain=True):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 12, H], fill=accent)
    d.text((140, 210), title, font=font("Bold", 76), fill=TEXT)
    d.text((140, 310), subtitle, font=font("Medium", 32), fill=MUTED)
    y = 420
    if chain:
        x = 140
        for i, label in enumerate(CHAIN):
            f = font("SemiBold", 28)
            tw = d.textlength(label, font=f)
            d.rounded_rectangle([x, y, x + tw + 36, y + 58], radius=29, fill=CARD, outline=LINE)
            d.text((x + 18, y + 12), label, font=f, fill=TEXT)
            x += tw + 36
            if i < len(CHAIN) - 1:
                d.text((x + 10, y + 10), "→", font=f, fill=accent)
                x += 46
        y += 120
    for line in lines:
        d.text((140, y), line, font=font("Regular", 28), fill=MUTED)
        y += 46
    return img


def outro_card(repo):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 12, H], fill=GREEN)
    d.text((140, 170), "Що показано", font=font("Bold", 64), fill=TEXT)
    rows = [
        ("Запит", "публічний реєстр — без токена і без згоди"),
        ("Право", "JWT із роллю; доступ визначає сервер за матрицею RBAC"),
        ("Згода", "окремо для маршруту і для звітів, записано на сервері"),
        ("Якість", "DQ-1: 472 м → 422; DQ-3: звіт мешканця чекає кворуму"),
        ("Передача", "кворум зібрано — статус застосовано в базі"),
        ("Сповіщення", "WebSocket: інший клієнт побачив зміну без оновлення"),
        ("Фіксація", "кожна дія в журналі; ланцюжок SHA-256 перевірено сервером"),
        ("Сценарій B", "403 DENIED_403_RBAC → той самий запис у консолі аудитора"),
    ]
    y = 290
    for label, text in rows:
        d.text((140, y), "✓", font=font("Bold", 30), fill=GREEN)
        d.text((190, y), label, font=font("SemiBold", 30), fill=TEXT)
        d.text((430, y), text, font=font("Regular", 30), fill=MUTED)
        y += 58
    d.text((140, y + 40), repo, font=font("Medium", 28), fill=BLUE)
    d.text(
        (140, y + 86),
        "FastAPI · PostgreSQL 16 · Leaflet · команда corelogic, ОІ-33, НУ «Львівська політехніка»",
        font=font("Regular", 24),
        fill=DIM,
    )
    return img


# ---------- encoding ----------


def encode(stills, out, fade=0.35):
    """stills: [(png, seconds)] → один mp4 з fade in/out на краях."""
    listing = out.with_suffix(".txt")
    total = sum(s for _, s in stills)
    with listing.open("w") as f:
        for png, sec in stills:
            f.write(f"file '{png.as_posix()}'\nduration {sec:.3f}\n")
        f.write(f"file '{stills[-1][0].as_posix()}'\n")
    tmp = out.with_name(out.stem + ".tmp.mp4")
    vf = (
        f"fps={FPS},format=yuv420p,"
        f"fade=t=in:st=0:d={fade},fade=t=out:st={total - fade:.3f}:d={fade}"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-vf",
            vf,
            "-t",
            f"{total:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            str(tmp),
        ],
        check=True,
    )
    tmp.rename(out)
    return total


def build(capture, output, repo, preview=None):
    work = Path(tempfile.mkdtemp(prefix="sg17_"))
    if capture.suffix == ".zip":
        with zipfile.ZipFile(capture) as z:
            z.extractall(work / "capture")
        capture = work / "capture"
    meta = json.loads((capture / "capture.json").read_text(encoding="utf-8"))
    frames_dir = capture / "frames"
    shots, events = meta["shots"], meta["events"]

    # Порядок у відео: за кроками; всередині кроку — як знімали
    ordered = sorted(enumerate(shots), key=lambda p: (STEP_ORDER.index(p[1]["step"]), p[0]))
    last_t = {}
    for _, shot in sorted(enumerate(shots), key=lambda p: p[1]["t"]):
        prev = last_t.get(shot["actor"], -1.0)
        shot["_events"] = relevant(events, shot, prev)
        last_t[shot["actor"]] = shot["t"]
    stills_dir = work / "stills"
    stills_dir.mkdir()

    scenes = []
    intro = title_card(
        "SkyGuard — демонстрація прототипу",
        "Керований обмін геоданими про укриття · резервне відео SG-17",
        [
            "Запис справжньої роботи прототипу: FastAPI + PostgreSQL + Leaflet.",
            "Праворуч у кадрі — фактичні запити й відповіді сервера, записані під час зйомки.",
            "Сценарій A — 7 кроків керованого обміну. Сценарій B — відмова 403 і запис в аудиті.",
        ],
    )
    scenes.append(("00_intro", [(intro, 8.0)]))

    # Кружечок кліку має сенс, лише якщо результат кліку — наступний кадр у ролику
    video = [shot for _, shot in ordered]
    by_time = sorted(video, key=lambda sh: sh["t"])
    for shot in video:
        if not shot.get("click"):
            continue
        later = [sh for sh in by_time if sh["actor"] == shot["actor"] and sh["t"] > shot["t"]]
        pos = video.index(shot)
        if not later or pos + 1 >= len(video) or video[pos + 1] is not later[0]:
            shot["click"] = None

    by_step = {}
    for _, shot in ordered:
        by_step.setdefault(shot["step"], []).append(shot)
    for step in STEP_ORDER:
        if step == "B":
            card = title_card(
                "Сценарій B",
                "Відмова 403 і запис в аудиті",
                [
                    "Мешканка запитує дані класу CONFIDENTIAL — службові контакти коменданта.",
                    "Сервер відмовляє і спершу записує інцидент у журнал аудиту.",
                ],
                accent=RED,
                chain=False,
            )
            scenes.append(("80_b_card", [(card, 4.5)]))
        stills = []
        history = []  # картки панелі в межах кроку
        for shot in by_step.get(step, []):
            fresh = [describe(e) for e in shot["_events"]]
            fresh_heads = {h for h, _, _ in fresh}
            history = [(h, c, ls, False) for h, c, ls, _ in history if h not in fresh_heads]
            history = [(h, c, ls, True) for h, c, ls in reversed(fresh)] + history
            hold = (shot.get("hold") or 3.0) * PACE
            # Кружечок кліку — в останню секунду кадру, перед переходом до результату
            if shot.get("click"):
                stills.append((compose_shot(frames_dir, shot, history, False), hold - 1.1))
                stills.append((compose_shot(frames_dir, shot, history, True), 1.1))
            else:
                stills.append((compose_shot(frames_dir, shot, history, False), hold))
        key = f"{STEP_ORDER.index(step) + 1:02d}_step_{step}"
        scenes.append((key, stills))
    scenes.append(("99_outro", [(outro_card(repo), 8.0)]))

    if preview:
        Path(preview).mkdir(parents=True, exist_ok=True)
        for key, stills in scenes:
            for i, (img, _) in enumerate(stills):
                img.save(Path(preview) / f"{key}_{i}.jpg", quality=88)
        return None

    parts, total = [], 0.0
    for key, stills in scenes:
        files = []
        for i, (img, sec) in enumerate(stills):
            png = stills_dir / f"{key}_{i:02d}.png"
            img.save(png)
            files.append((png, sec))
        part = work / f"{key}.mp4"
        total += encode(files, part)
        parts.append(part)
    concat = work / "parts.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    tmp = Path(output).with_name(Path(output).stem + ".tmp.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(tmp),
        ],
        check=True,
    )
    tmp.rename(output)
    shutil.rmtree(work)
    return total


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("capture", type=Path, help="demo_capture.zip або розпакована папка")
    ap.add_argument("-o", "--output", default="SkyGuard_demo_SG-17.mp4")
    ap.add_argument("--repo", default="github.com/Taras-Klichkovskyi/skyguard")
    ap.add_argument("--preview", help="лише зберегти кадри-композиції в цю папку, без відео")
    args = ap.parse_args()
    total = build(args.capture, args.output, args.repo, args.preview)
    if total:
        print(f"{args.output}: {total:.1f} с")


if __name__ == "__main__":
    main()

"""Зберігає специфікацію OpenAPI у docs/openapi.json (для фронтенду та звіту).

python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

target = ROOT / "docs" / "openapi.json"
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{target.relative_to(ROOT)}: {len(app.openapi()['paths'])} шляхів")

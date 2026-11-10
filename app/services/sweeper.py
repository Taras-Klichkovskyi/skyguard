"""Фонове завдання: анулює краудсорс-звіти, що не зібрали кворум вчасно (DQ-3).

Звіти анулюються і без нього — щоразу, коли про те саме укриття надходить
новий звіт. Завдання прибирає ті, після яких нових звітів не було.
"""

import asyncio
import logging
from datetime import UTC, datetime

from starlette.concurrency import run_in_threadpool

from app.db.session import SessionLocal
from app.services.status import expire_pending

logger = logging.getLogger(__name__)


def sweep_once() -> int:
    with SessionLocal() as db:
        expired = expire_pending(db, datetime.now(UTC))
        db.commit()
    return expired


async def run_forever(interval_s: int) -> None:
    while True:
        await asyncio.sleep(interval_s)
        try:
            expired = await run_in_threadpool(sweep_once)
            if expired:
                logger.info("expired %d pending status reports", expired)
        except Exception:
            logger.exception("sweep failed")  # наступна спроба — за інтервал

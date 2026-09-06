"""
הקובץ מפעיל סנכרון אוטומטי של קובצי המקור ברקע

הסנכרון משתמש בתהליך הסנכרון הקיים
ומריץ אותו במרווחי זמן קבועים ללא תלות בערוץ התקשורת

לאחר כל סנכרון ניתן להפעיל פעולה נוספת
כדי לרענן את הנתונים שבהם משתמשת המערכת
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from ingestion.storage_sync import (
    synchronize_storage,
)


DEFAULT_SYNC_INTERVAL_SECONDS = 60.0

CHANGE_KEYS = (
    "added",
    "replaced",
    "deleted",
)


def _has_meaningful_changes(
    changes: dict[str, list[str]],
) -> bool:
    """
    בודקת אם נמצאו שינויים שמצריכים עדכון נתונים

    קבצים ללא שינוי אינם נחשבים לשינוי פעיל
    """

    return any(
        changes.get(
            key,
            [],
        )
        for key in CHANGE_KEYS
    )


async def synchronize_storage_once(
    *,
    refresh_data: Callable[[], Any] | None = None,
) -> dict[str, list[str]]:
    """
    מבצעת סנכרון אחד בלי לחסום את לולאת האירועים

    לאחר סיום הסנכרון ניתן לרענן את נתוני המערכת
    כדי שהשינויים יהיו זמינים מיד לשכבת החיפוש
    """

    changes = await asyncio.to_thread(
        synchronize_storage
    )

    if refresh_data is not None:
        await asyncio.to_thread(
            refresh_data
        )

    return changes


async def run_storage_sync_loop(
    *,
    refresh_data: Callable[[], Any] | None = None,
    interval_seconds: float = DEFAULT_SYNC_INTERVAL_SECONDS,
) -> None:
    """
    מפעילה סנכרון מחזורי של קובצי המקור

    כל מחזור מסתיים לפני שהמחזור הבא מתחיל
    ולכן לא נוצרים שני תהליכי סנכרון במקביל
    """

    if interval_seconds <= 0:
        raise ValueError(
            "מרווח הסנכרון חייב להיות גדול מאפס"
        )

    while True:
        try:
            changes = await synchronize_storage_once(
                refresh_data=refresh_data
            )

            if _has_meaningful_changes(
                changes
            ):
                print(
                    "סנכרון קובצי המקור "
                    "הסתיים ונמצאו שינויים"
                )

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(
                "שגיאה בסנכרון קובצי המקור:",
                repr(
                    error
                ),
            )

        await asyncio.sleep(
            interval_seconds
        )
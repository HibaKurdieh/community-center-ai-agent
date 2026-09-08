"""
הקובץ אחראי על העבודה עם מקורות חיצוניים במסד הנתונים

הוא מאפשר לקרוא להוסיף לעדכן ולמחוק מקורות
וכן לשמור את מצב הסנכרון האחרון של כל מקור
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database.supabase_client import (
    get_supabase_client,
)


TABLE_NAME = "external_sources"


def _utc_now() -> str:
    """
    מחזירה את הזמן הנוכחי בפורמט אחיד
    לצורך שמירת זמני עדכון במסד הנתונים
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def get_all_external_sources() -> list[dict[str, Any]]:
    """
    קוראת את כל המקורות החיצוניים
    לפי סדר היצירה שלהם
    """

    client = get_supabase_client()

    response = (
        client.table(
            TABLE_NAME
        )
        .select("*")
        .order("id")
        .execute()
    )

    return response.data or []


def get_active_external_sources() -> list[dict[str, Any]]:
    """
    קוראת רק מקורות חיצוניים פעילים
    שמיועדים להשתתף בתהליך הסנכרון
    """

    client = get_supabase_client()

    response = (
        client.table(
            TABLE_NAME
        )
        .select("*")
        .eq(
            "is_active",
            True,
        )
        .order("id")
        .execute()
    )

    return response.data or []


def get_external_source_by_id(
    source_id: int,
) -> dict[str, Any] | None:
    """
    קוראת מקור חיצוני יחיד
    לפי המזהה שלו במסד הנתונים
    """

    client = get_supabase_client()

    response = (
        client.table(
            TABLE_NAME
        )
        .select("*")
        .eq(
            "id",
            source_id,
        )
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return None

    return rows[0]


def create_external_source(
    *,
    name: str,
    url: str,
    source_type: str = "publuu",
    is_active: bool = True,
) -> dict[str, Any]:
    """
    שומרת מקור חיצוני חדש
    ומחזירה את הרשומה שנוצרה
    """

    clean_name = name.strip()
    clean_url = url.strip()
    clean_source_type = source_type.strip()

    if not clean_name:
        raise ValueError(
            "שם המקור אינו יכול להיות ריק"
        )

    if not clean_url:
        raise ValueError(
            "כתובת המקור אינה יכולה להיות ריקה"
        )

    if not clean_source_type:
        raise ValueError(
            "סוג המקור אינו יכול להיות ריק"
        )

    client = get_supabase_client()

    response = (
        client.table(
            TABLE_NAME
        )
        .insert(
            {
                "name": clean_name,
                "url": clean_url,
                "source_type": clean_source_type,
                "is_active": is_active,
                "updated_at": _utc_now(),
            }
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise RuntimeError(
            "המקור החיצוני לא נשמר"
        )

    return rows[0]


def update_external_source(
    source_id: int,
    *,
    name: str,
    url: str,
    source_type: str,
    is_active: bool,
) -> dict[str, Any]:
    """
    מעדכנת את פרטי המקור החיצוני
    בלי לשנות את היסטוריית הסנכרון שלו
    """

    clean_name = name.strip()
    clean_url = url.strip()
    clean_source_type = source_type.strip()

    if not clean_name:
        raise ValueError(
            "שם המקור אינו יכול להיות ריק"
        )

    if not clean_url:
        raise ValueError(
            "כתובת המקור אינה יכולה להיות ריקה"
        )

    if not clean_source_type:
        raise ValueError(
            "סוג המקור אינו יכול להיות ריק"
        )

    client = get_supabase_client()

    response = (
        client.table(
            TABLE_NAME
        )
        .update(
            {
                "name": clean_name,
                "url": clean_url,
                "source_type": clean_source_type,
                "is_active": is_active,
                "updated_at": _utc_now(),
            }
        )
        .eq(
            "id",
            source_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise ValueError(
            "המקור החיצוני לא נמצא"
        )

    return rows[0]


def delete_external_source(
    source_id: int,
) -> bool:
    """
    מוחקת מקור חיצוני לפי המזהה שלו
    ומחזירה אם אכן נמחקה רשומה
    """

    client = get_supabase_client()

    response = (
        client.table(
            TABLE_NAME
        )
        .delete()
        .eq(
            "id",
            source_id,
        )
        .execute()
    )

    return bool(
        response.data
    )


def update_external_source_sync_status(
    source_id: int,
    *,
    status: str,
    content_hash: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """
    מעדכנת את מצב הסנכרון האחרון של המקור

    הפעולה שומרת את זמן הסנכרון
    את טביעת התוכן ואת הודעת השגיאה במקרה הצורך
    """

    clean_status = status.strip()

    if not clean_status:
        raise ValueError(
            "מצב הסנכרון אינו יכול להיות ריק"
        )

    payload: dict[str, Any] = {
        "last_status": clean_status,
        "last_synced_at": _utc_now(),
        "last_error": error_message,
        "updated_at": _utc_now(),
    }

    if content_hash is not None:
        payload[
            "last_content_hash"
        ] = content_hash

    client = get_supabase_client()

    response = (
        client.table(
            TABLE_NAME
        )
        .update(
            payload
        )
        .eq(
            "id",
            source_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise ValueError(
            "המקור החיצוני לא נמצא"
        )

    return rows[0]

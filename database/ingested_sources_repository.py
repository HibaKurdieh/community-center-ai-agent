"""
הקובץ אחראי על ניהול קובצי המקור שכבר עובדו

הוא מאפשר לבדוק אם תוכן של קובץ כבר עבר עיבוד
ולשמור את פרטי הקובץ לאחר סיום תהליך הקליטה בהצלחה

הזיהוי מתבצע לפי טביעת התוכן של הקובץ
ולא לפי שם הקובץ בלבד
"""

from __future__ import annotations

from typing import Any

from database.supabase_client import (
    get_supabase_client,
)


TABLE_NAME = "ingested_sources"


def is_source_processed(
    file_hash: str,
) -> bool:
    """
    בודקת אם טביעת התוכן כבר קיימת במסד הנתונים

    מוחזר ערך חיובי רק כאשר הקובץ
    כבר סומן כקובץ שעובד בהצלחה
    """

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("id")
        .eq(
            "file_hash",
            file_hash,
        )
        .eq(
            "status",
            "processed",
        )
        .limit(1)
        .execute()
    )

    return bool(
        response.data
    )


def get_processed_sources() -> list[dict[str, Any]]:
    """
    קוראת את מקורות הנתונים שכבר עובדו

    לכל מקור מוחזרים שם הקובץ
    טביעת התוכן והסטטוס שלו
    """

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select(
            "source_file,"
            "file_hash,"
            "source_type,"
            "activities_count,"
            "status"
        )
        .eq(
            "status",
            "processed",
        )
        .execute()
    )

    return response.data or []


def register_processed_source(
    *,
    source_file: str,
    file_hash: str,
    activities_count: int,
    source_type: str = "docx",
) -> None:
    """
    שומרת במסד הנתונים שקובץ המקור עובד בהצלחה

    יחד עם טביעת התוכן נשמרים
    שם הקובץ ומספר הפעילויות שחולצו ממנו
    """

    client = get_supabase_client()

    record = {
        "source_file": source_file,
        "file_hash": file_hash,
        "source_type": source_type,
        "activities_count": (
            activities_count
        ),
        "status": "processed",
    }

    (
        client.table(TABLE_NAME)
        .upsert(
            record,
            on_conflict="file_hash",
        )
        .execute()
    )


def delete_processed_source_by_name(
    source_file: str,
) -> int:
    """
    מוחקת את רישומי העיבוד ששייכים לקובץ מקור מסוים

    הפעולה מתבצעת לפי שם קובץ המקור
    ומחזירה את מספר הרשומות שנמחקו
    """

    clean_source_file = (
        source_file.strip()
    )

    if not clean_source_file:
        raise ValueError(
            "שם קובץ המקור אינו יכול להיות ריק"
        )

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .delete()
        .eq(
            "source_file",
            clean_source_file,
        )
        .execute()
    )

    return len(
        response.data or []
    )
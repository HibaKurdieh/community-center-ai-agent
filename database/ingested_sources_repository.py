"""
הקובץ אחראי על ניהול קובצי המקור שכבר עובדו

הוא מאפשר לבדוק אם תוכן של קובץ כבר עבר עיבוד
ולשמור את פרטי הקובץ לאחר סיום תהליך הקליטה בהצלחה

הזיהוי מתבצע לפי טביעת התוכן של הקובץ
ולא לפי שם הקובץ בלבד
"""

from __future__ import annotations

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
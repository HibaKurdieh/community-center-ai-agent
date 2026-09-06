"""
הקובץ אחראי על העבודה עם טבלת הפעילויות במסד הנתונים

הוא מכין את הרשומות לפני שמירה
בודק שדות חובה ומונע הכנסת כפילויות

בנוסף הוא מאפשר לקרוא את הפעילויות הקיימות
לצורך שימוש בשכבת החיפוש של המערכת
"""

from __future__ import annotations

from typing import Any

from database.supabase_client import (
    get_supabase_client,
)


TABLE_NAME = "activities"


# השדות שקיימים בטבלת הפעילויות במסד הנתונים
ACTIVITY_FIELDS = (
    "source_file",
    "center_name",
    "branch",
    "day",
    "raw_day",
    "start_time",
    "end_time",
    "end_time_source",
    "raw_time",
    "name",
    "raw_name",
    "english_name",
    "instructor",
    "location",
    "target_audience",
    "min_age",
    "max_age",
    "capacity",
    "level",
    "notes",
    "season",
    "valid_from",
    "source_language",
    "status",
)


# השדות שחייבים להכיל ערך לפני שמירת פעילות
REQUIRED_FIELDS = (
    "source_file",
    "center_name",
    "day",
    "raw_day",
    "start_time",
    "name",
    "raw_name",
    "target_audience",
    "source_language",
    "status",
)


def _has_value(
    value: Any,
) -> bool:
    """
    בודקת אם קיים ערך שימושי בשדה
    """

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    יוצרת מפתח לזיהוי פעילות כפולה

    שם קובץ המקור אינו חלק מהמפתח
    כדי שאותה פעילות ממקור אחר לא תישמר פעמיים
    """

    return (
        activity.get("center_name"),
        activity.get("branch"),
        activity.get("day"),
        activity.get("start_time"),
        activity.get("end_time"),
        activity.get("name"),
        activity.get("instructor"),
        activity.get("location"),
    )


def _validate_activity(
    activity: dict[str, Any],
) -> None:
    """
    בודקת שכל השדות החיוניים קיימים
    לפני שליחת הפעילות למסד הנתונים
    """

    missing = [
        field
        for field in REQUIRED_FIELDS
        if not _has_value(
            activity.get(field)
        )
    ]

    if missing:
        raise ValueError(
            "Activity is missing required fields: "
            + ", ".join(missing)
        )


def _prepare_activity(
    activity: dict[str, Any],
) -> dict[str, Any]:
    """
    מכינה את הפעילות לשמירה במסד הנתונים

    בודקת את השדות החיוניים
    ושומרת רק שדות שקיימים בטבלה
    """

    _validate_activity(activity)

    return {
        field: activity.get(field)
        for field in ACTIVITY_FIELDS
    }


def get_existing_activity_keys(
    client=None,
) -> set[tuple[Any, ...]]:
    """
    קוראת את הפעילויות הקיימות במסד הנתונים
    ויוצרת מהן מפתחות לצורך זיהוי כפילויות
    """

    if client is None:
        client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select(
            "center_name,"
            "branch,"
            "day,"
            "start_time,"
            "end_time,"
            "name,"
            "instructor,"
            "location"
        )
        .execute()
    )

    existing = response.data or []

    return {
        _activity_key(activity)
        for activity in existing
    }


def insert_new_activities(
    activities: list[dict[str, Any]],
) -> dict[str, int]:
    """
    שומרת במסד הנתונים רק פעילויות חדשות

    הפונקציה משווה את הפעילויות לרשומות שכבר קיימות
    ומונעת כפילויות גם מול מסד הנתונים
    וגם בתוך קבוצת הנתונים החדשה

    בסיום מוחזר סיכום של מספר הרשומות שהתקבלו
    נשמרו או זוהו ככפולות
    """

    if not activities:
        return {
            "received": 0,
            "inserted": 0,
            "duplicates": 0,
        }

    client = get_supabase_client()

    existing_keys = (
        get_existing_activity_keys(
            client
        )
    )

    new_records: list[
        dict[str, Any]
    ] = []

    seen_in_batch: set[
        tuple[Any, ...]
    ] = set()

    duplicates = 0

    for activity in activities:
        prepared = _prepare_activity(
            activity
        )

        key = _activity_key(
            prepared
        )

        if (
            key in existing_keys
            or key in seen_in_batch
        ):
            duplicates += 1
            continue

        seen_in_batch.add(key)

        new_records.append(
            prepared
        )

    if not new_records:
        return {
            "received": len(activities),
            "inserted": 0,
            "duplicates": duplicates,
        }

    response = (
        client.table(TABLE_NAME)
        .insert(new_records)
        .execute()
    )

    inserted = len(
        response.data or []
    )

    return {
        "received": len(activities),
        "inserted": inserted,
        "duplicates": duplicates,
    }


def get_activities_by_source_file(
    source_file: str,
) -> list[dict[str, Any]]:
    """
    קוראת את כל הפעילויות ששייכות לקובץ מקור מסוים

    התוצאה משמשת לשמירת עותק של הנתונים הקיימים
    לפני החלפה של קובץ מקור
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
        .select("*")
        .eq(
            "source_file",
            clean_source_file,
        )
        .order("id")
        .execute()
    )

    return response.data or []


def delete_activities_by_source_file(
    source_file: str,
) -> int:
    """
    מוחקת את כל הפעילויות ששייכות לקובץ מקור מסוים

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


def get_all_activities() -> list[dict[str, Any]]:
    """
    קוראת את כל הפעילויות מטבלת הפעילויות
    ומחזירה אותן לשימוש בשכבת החיפוש
    """

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .order("id")
        .execute()
    )

    return response.data or []

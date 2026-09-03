"""
הקובץ מנהל קליטת נתונים ממקורות מובנים נוספים

הוא מטפל בקובצי גיליון ובמקורות נתונים חיצוניים

כל מקור עובר התאמה למבנה הפעילות האחיד
לאחר מכן מתבצעת בדיקת תקינות
ולבסוף מוסרות רשומות כפולות
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ingestion.readers.excel_reader import (
    SUPPORTED_EXCEL_SUFFIXES,
    read_excel_activities,
)
from ingestion.readers.external_api_reader import (
    read_external_activities,
)
from ingestion.validation import (
    keep_valid_activities,
    validate_activities,
)


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    יוצרת מפתח אחיד
    לצורך זיהוי רשומות כפולות
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


def _deduplicate_activities(
    activities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    מסירה רשומות כפולות
    מתוך רשימת הפעילויות
    """

    seen: set[
        tuple[Any, ...]
    ] = set()

    unique: list[
        dict[str, Any]
    ] = []

    for activity in activities:

        key = _activity_key(
            activity
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            activity
        )

    return unique


def _validate_source_activities(
    activities: list[dict[str, Any]],
    *,
    source_label: str,
) -> list[dict[str, Any]]:
    """
    בודקת את תקינות הפעילויות
    ושומרת רק רשומות ללא שגיאות קריטיות
    """

    report = validate_activities(
        activities
    )

    print(
        f"\nבדיקת מקור "
        f"{source_label}"
    )

    print(
        "רשומות תקינות",
        f"{report.valid_records}/"
        f"{report.total_records}",
    )

    print(
        "שגיאות קריטיות",
        len(
            report.critical_errors
        ),
    )

    print(
        "אזהרות",
        len(
            report.warnings
        ),
    )

    if report.critical_errors:

        print(
            "\nשגיאות ראשונות"
        )

        for error in (
            report.critical_errors[
                :10
            ]
        ):
            print(
                "-",
                error,
            )

    valid_activities = (
        keep_valid_activities(
            activities,
            report,
        )
    )

    if (
        activities
        and not valid_activities
    ):
        raise ValueError(
            f"לא נמצאו פעילויות תקינות "
            f"במקור {source_label}"
        )

    return _deduplicate_activities(
        valid_activities
    )


def ingest_structured_file(
    file_path: str | Path,
    *,
    sheet_name: str | None = None,
    default_center_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    קוראת קובץ גיליון
    ומעבירה אותו דרך תהליך ההתאמה והבדיקה
    """

    path = Path(
        file_path
    ).resolve()

    if not path.exists():
        raise FileNotFoundError(
            path
        )

    if (
        path.suffix.lower()
        not in SUPPORTED_EXCEL_SUFFIXES
    ):
        raise ValueError(
            "סוג הקובץ אינו נתמך "
            "במסלול הנתונים המובנים"
        )

    activities = (
        read_excel_activities(
            path,
            sheet_name=sheet_name,
            default_center_name=(
                default_center_name
            ),
        )
    )

    print(
        f"\nקובץ גיליון "
        f"{path.name}"
    )

    return _validate_source_activities(
        activities,
        source_label=path.name,
    )


def ingest_external_source(
    api_url: str,
    *,
    api_key: str | None = None,
    source_name: str = "external_api",
    default_center_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    קוראת פעילויות ממקור נתונים חיצוני
    ומעבירה אותן דרך תהליך ההתאמה והבדיקה
    """

    activities = (
        read_external_activities(
            api_url,
            api_key=api_key,
            source_name=source_name,
            default_center_name=(
                default_center_name
            ),
        )
    )

    print(
        f"\nמקור חיצוני "
        f"{source_name}"
    )

    return _validate_source_activities(
        activities,
        source_label=source_name,
    )
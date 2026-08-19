from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ingestion.parsers.basic_schedule_parser import (
    parse_basic_schedule,
)
from ingestion.parsers.table_schedule_parser import (
    parse_table_schedule,
)
from ingestion.parsers.dirty_schedule_parser import (
    parse_dirty_schedule,
)
from ingestion.parsers.bilingual_schedule_parser import (
    parse_bilingual_schedule,
)
from ingestion.parsers.grouped_schedule_parser import (
    parse_grouped_schedule,
)
from ingestion.parsers.edge_case_schedule_parser import (
    parse_edge_case_schedule,
)


LECTURER_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "lecturer_samples"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "activities_from_lecturer.json"
)


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    מפתח לזיהוי כפילויות בין הרשומות.
    """

    return (
        activity.get("source_file"),
        activity.get("day"),
        activity.get("start_time"),
        activity.get("end_time"),
        activity.get("name"),
        activity.get("instructor"),
        activity.get("location"),
    )


def deduplicate_activities(
    activities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    מסיר כפילויות מהתוצאה המאוחדת.
    """

    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []

    for activity in activities:
        key = _activity_key(activity)

        if key in seen:
            continue

        seen.add(key)
        unique.append(activity)

    return unique


def ingest_all_documents() -> list[dict[str, Any]]:
    """
    מריץ את ה-parser המתאים על כל אחד
    מששת קבצי המרצה ומאחד את התוצאות.
    """

    files_and_parsers = [
        (
            "01_מרכז_ספורט_הדס_בסיסי.docx",
            parse_basic_schedule,
        ),
        (
            "02_מרכז_ספורט_אלונים_טבלה.docx",
            parse_table_schedule,
        ),
        (
            "03_מרכז_כושר_נופים_מלוכלך.docx",
            parse_dirty_schedule,
        ),
        (
            "04_Neve_Sport_Center_bilingual.docx",
            parse_bilingual_schedule,
        ),
        (
            "05_מרכז_ספורט_מעיין_לפי_חוג.docx",
            parse_grouped_schedule,
        ),
        (
            "06_מרכז_ספורט_גלים_מקרי_קצה.docx",
            parse_edge_case_schedule,
        ),
    ]

    all_activities: list[dict[str, Any]] = []

    print("\n=== Document Ingestion Pipeline ===\n")

    for filename, parser in files_and_parsers:
        file_path = (
            LECTURER_DATA_DIR
            / filename
        )

        if not file_path.exists():
            print(
                f"⚠ קובץ לא נמצא: {filename}"
            )
            continue

        activities = parser(
            file_path
        )

        all_activities.extend(
            activities
        )

        print(
            f"{filename}: "
            f"{len(activities)} שיעורים"
        )

    unique_activities = deduplicate_activities(
        all_activities
    )

    return unique_activities


def save_activities(
    activities: list[dict[str, Any]],
) -> None:
    """
    שומר את כל הפעילויות לקובץ JSON אחיד.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            activities,
            file,
            ensure_ascii=False,
            indent=2,
        )


def print_summary(
    activities: list[dict[str, Any]],
) -> None:
    """
    מדפיס סיכום קצר של תוצאת ה-ingestion.
    """

    print("\n" + "—" * 60)

    print(
        "סה\"כ שיעורים לאחר איחוד:",
        len(activities),
    )

    counts_by_source: dict[str, int] = {}

    for activity in activities:
        source_file = activity.get(
            "source_file",
            "unknown",
        )

        counts_by_source[source_file] = (
            counts_by_source.get(
                source_file,
                0,
            )
            + 1
        )

    print("\nלפי קובץ:")

    for source_file, count in sorted(
        counts_by_source.items()
    ):
        print(
            f"- {source_file}: {count}"
        )

    cancelled = sum(
        1
        for activity in activities
        if activity.get("status") == "cancelled"
    )

    tbd = sum(
        1
        for activity in activities
        if activity.get("status") == "tbd"
    )

    missing_instructor = sum(
        1
        for activity in activities
        if not activity.get("instructor")
    )

    missing_location = sum(
        1
        for activity in activities
        if not activity.get("location")
    )

    print("\nאיכות נתונים:")
    print(
        "- cancelled:",
        cancelled,
    )
    print(
        "- tbd:",
        tbd,
    )
    print(
        "- ללא מדריך:",
        missing_instructor,
    )
    print(
        "- ללא מיקום:",
        missing_location,
    )

    print(
        "\nנשמר:",
        OUTPUT_FILE,
    )


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(
                encoding="utf-8"
            )
        except (AttributeError, OSError):
            pass

    activities = ingest_all_documents()

    save_activities(
        activities
    )

    print_summary(
        activities
    )


if __name__ == "__main__":
    main()
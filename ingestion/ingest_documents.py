"""
הקובץ מנהל את תהליך קליטת כל מסמכי המקור

הוא מאתר את כל המסמכים בתיקייה
מעביר כל מסמך דרך תהליך הפענוח
מאחד את הפעילויות ומסיר כפילויות

רק כאשר מתבקש לבצע שמירה
הפעילויות מועברות לשכבת מסד הנתונים
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Any


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.activities_repository import (
    insert_new_activities,
)
from ingestion.universal_docx_parser import (
    parse_universal_docx,
)
LECTURER_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "lecturer_samples"
)


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    מפתח לזיהוי כפילויות בין הרשומות.
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
    Automatically discovers all DOCX files in the
    lecturer data directory and processes each one
    through the universal parser.

    No filename-to-parser mapping is required.
    """

    file_paths = sorted(
        LECTURER_DATA_DIR.glob("*.docx")
    )

    if not file_paths:
        print(
            "⚠ No DOCX files found."
        )
        return []

    all_activities: list[
        dict[str, Any]
    ] = []

    print(
        "\n=== Universal Document Ingestion Pipeline ===\n"
    )

    for file_path in file_paths:

        (
            activities,
            parser_name,
            attempts,
        ) = parse_universal_docx(
            file_path
        )

        all_activities.extend(
            activities
        )

        print(
            f"{file_path.name}: "
            f"{len(activities)} activities "
            f"| parser={parser_name}"
        )

    return deduplicate_activities(
        all_activities
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


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(
                encoding="utf-8"
            )
        except (
            AttributeError,
            OSError,
        ):
            pass

    parser = argparse.ArgumentParser(
        description=(
            "Universal batch ingestion "
            "for lecturer DOCX files."
        )
    )

    parser.add_argument(
        "--save",
        action="store_true",
        help=(
            "Save newly extracted activities "
            "directly to Supabase."
        ),
    )

    args = parser.parse_args()

    activities = (
        ingest_all_documents()
    )

    print_summary(
        activities
    )

    if not args.save:
        print(
            "\nDRY RUN: "
            "Nothing was written to Supabase."
        )
        return

    print(
        "\nSaving to Supabase..."
    )

    stats = insert_new_activities(
        activities
    )

    print(
        "\n=== Supabase Result ==="
    )

    print(
        "Received:",
        stats["received"],
    )

    print(
        "Inserted:",
        stats["inserted"],
    )

    print(
        "Duplicates:",
        stats["duplicates"],
    )

if __name__ == "__main__":
    main()
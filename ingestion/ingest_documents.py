"""
הקובץ מנהל את תהליך קליטת מקורות הנתונים

המערכת תומכת בקובצי מסמכים קובצי אקסל
ובמקור חיצוני המחזיר נתונים מובנים

כל מקור מועבר למסלול העיבוד המתאים לו
והפעילויות מומרות למבנה אחיד נבדקות ומסוננות מכפילויות

רק כאשר מתבקש לבצע שמירה
הפעילויות מועברות לשכבת מסד הנתונים
"""

from __future__ import annotations

import argparse
import os
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
from database.ingested_sources_repository import (
    is_source_processed,
    register_processed_source,
)
from ingestion.ai_docx_parser import (
    parse_ai_docx,
)
from ingestion.file_hash import (
    calculate_file_hash,
)
from ingestion.source_ingestion import (
    ingest_external_source,
    ingest_structured_file,
)
from ingestion.storage_source import (
    downloaded_source_files,
)


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    מפתח לזיהוי כפילויות בין הרשומות
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
    מסירה כפילויות מהתוצאה המאוחדת
    """

    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []

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


def _process_docx_file(
    file_path: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any] | None,
]:
    """
    מעבדת קובץ וורד לפי טביעת התוכן שלו

    אם טביעת התוכן כבר קיימת במסד הנתונים
    הקובץ אינו נשלח שוב למודל השפה

    אם הקובץ חדש הוא עובר את מסלול הפענוח
    ורק תוצאה תקינה מוחזרת להמשך התהליך
    """

    file_hash = calculate_file_hash(
        file_path
    )

    if is_source_processed(
        file_hash
    ):
        print(
            f"{file_path.name}: "
            "already processed, skipping AI."
        )

        return [], None

    activities = parse_ai_docx(
        file_path
    )

    if not activities:
        print(
            f"{file_path.name}: "
            "no valid activities extracted."
        )

        return [], None

    source_record = {
        "source_file": file_path.name,
        "file_hash": file_hash,
        "activities_count": len(
            activities
        ),
        "source_type": "docx",
    }

    return (
        activities,
        source_record,
    )


def ingest_all_documents() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    מורידה את כל קובצי המקור ממאגר הקבצים

    כל קובץ מועבר למסלול העיבוד המתאים לפי סוגו

    קובץ שכבר עובד בעבר מזוהה לפי טביעת התוכן
    ואינו עובר עיבוד חוזר ללא צורך
    """

    all_activities: list[
        dict[str, Any]
    ] = []

    processed_sources: list[
        dict[str, Any]
    ] = []

    print(
        "\n"
        "=== Storage Ingestion Pipeline ==="
        "\n"
    )

    with downloaded_source_files() as file_paths:

        if not file_paths:
            print(
                "⚠ No supported source files found."
            )

            return [], []

        for file_path in sorted(
            file_paths
        ):

            suffix = (
                file_path.suffix.lower()
            )

            if suffix == ".docx":
                (
                    activities,
                    source_record,
                ) = _process_docx_file(
                    file_path
                )

            else:
                file_hash = (
                    calculate_file_hash(
                        file_path
                    )
                )

                if is_source_processed(
                    file_hash
                ):
                    print(
                        f"{file_path.name}: "
                        "already processed, skipping."
                    )

                    continue

                activities = (
                    ingest_structured_file(
                        file_path
                    )
                )

                source_record = {
                    "source_file":
                        file_path.name,
                    "file_hash":
                        file_hash,
                    "activities_count":
                        len(
                            activities
                        ),
                    "source_type":
                        suffix.lstrip("."),
                }

            if not activities:
                continue

            all_activities.extend(
                activities
            )

            if source_record is not None:
                processed_sources.append(
                    source_record
                )

            print(
                f"{file_path.name}: "
                f"{len(activities)} activities"
            )

    return (
        deduplicate_activities(
            all_activities
        ),
        processed_sources,
    )

def print_summary(
    activities: list[dict[str, Any]],
) -> None:
    """
    מדפיסה סיכום קצר של תוצאת תהליך הקליטה
    """

    print(
        "\n" + "—" * 60
    )

    print(
        'סה"כ שיעורים לאחר איחוד:',
        len(activities),
    )

    counts_by_source: dict[
        str,
        int,
    ] = {}

    for activity in activities:
        source_file = activity.get(
            "source_file",
            "unknown",
        )

        counts_by_source[
            source_file
        ] = (
            counts_by_source.get(
                source_file,
                0,
            )
            + 1
        )

    print(
        "\nלפי קובץ:"
    )

    for source_file, count in sorted(
        counts_by_source.items()
    ):
        print(
            f"- {source_file}: {count}"
        )

    cancelled = sum(
        1
        for activity in activities
        if activity.get(
            "status"
        ) == "cancelled"
    )

    tbd = sum(
        1
        for activity in activities
        if activity.get(
            "status"
        ) == "tbd"
    )

    missing_instructor = sum(
        1
        for activity in activities
        if not activity.get(
            "instructor"
        )
    )

    missing_location = sum(
        1
        for activity in activities
        if not activity.get(
            "location"
        )
    )

    print(
        "\nאיכות נתונים:"
    )

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
            "Ingestion for DOCX, Excel "
            "and external structured sources."
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

    parser.add_argument(
        "--file",
        type=Path,
        help=(
            "Path to a DOCX or Excel file."
        ),
    )

    parser.add_argument(
        "--api-url",
        type=str,
    )

    parser.add_argument(
        "--sheet",
        type=str,
    )

    parser.add_argument(
        "--center-name",
        type=str,
    )

    parser.add_argument(
        "--source-name",
        type=str,
        default="external_api",
    )

    parser.add_argument(
        "--api-key-env",
        type=str,
        default="EXTERNAL_API_KEY",
    )

    args = parser.parse_args()

    processed_sources: list[
        dict[str, Any]
    ] = []

    if (
        args.file is not None
        and args.api_url
    ):
        raise ValueError(
            "יש לבחור מקור אחד בלבד "
            "קובץ או מקור חיצוני"
        )

    if args.file is not None:
        file_path = (
            args.file.resolve()
        )

        if not file_path.exists():
            raise FileNotFoundError(
                file_path
            )

        if (
            file_path.suffix.lower()
            == ".docx"
        ):
            (
                activities,
                source_record,
            ) = _process_docx_file(
                file_path
            )

            activities = (
                deduplicate_activities(
                    activities
                )
            )

            if source_record is not None:
                processed_sources.append(
                    source_record
                )

            print(
                f"\nExternal file: "
                f"{file_path.name}"
            )

            if activities:
                print(
                    "Document processed "
                    "with AI extraction."
                )

        else:
            activities = (
                ingest_structured_file(
                    file_path,
                    sheet_name=args.sheet,
                    default_center_name=(
                        args.center_name
                    ),
                )
            )

    elif args.api_url:
        api_key = os.getenv(
            args.api_key_env
        )

        activities = (
            ingest_external_source(
                args.api_url,
                api_key=api_key,
                source_name=(
                    args.source_name
                ),
                default_center_name=(
                    args.center_name
                ),
            )
        )

    else:
        (
            activities,
            processed_sources,
        ) = ingest_all_documents()

    print_summary(
        activities
    )

    if not args.save:
        print(
            "\nDRY RUN: "
            "Nothing was written "
            "to Supabase."
        )
        return

    print(
        "\nSaving to Supabase..."
    )

    stats = insert_new_activities(
        activities
    )

    for source in processed_sources:
        register_processed_source(
            source_file=source[
                "source_file"
            ],
            file_hash=source[
                "file_hash"
            ],
            activities_count=source[
                "activities_count"
            ],
            source_type=source.get(
                "source_type",
                "docx",
            ),
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

    if processed_sources:
        print(
            "Sources registered:",
            len(processed_sources),
        )


if __name__ == "__main__":
    main()

# python -m ingestion.ingest_documents --save
# python -m ingestion.ingest_documents --file "C:\...\file.xlsx" --save
# python -m ingestion.ingest_documents --api-url "https://..." --save
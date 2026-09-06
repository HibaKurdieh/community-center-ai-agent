"""
הקובץ מזהה ומסנכרן שינויים בקובצי המקור שנמצאים באחסון

המערכת משווה בין הקבצים הקיימים כעת באחסון
לבין המקורות שכבר סומנו כמעובדים במסד הנתונים

ניתן להפעיל בדיקה בלבד
או לבצע בפועל הוספה החלפה ומחיקה של מקורות
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


from database.activities_repository import (
    delete_activities_by_source_file,
    get_activities_by_source_file,
    insert_new_activities,
)
from database.ingested_sources_repository import (
    delete_processed_source_by_name,
    get_processed_sources,
    register_processed_source,
)
from ingestion.ai_docx_parser import (
    parse_ai_docx,
)
from ingestion.file_hash import (
    calculate_file_hash,
)
from ingestion.readers.excel_reader import (
    SUPPORTED_EXCEL_SUFFIXES,
)
from ingestion.source_ingestion import (
    ingest_structured_file,
)
from ingestion.storage_source import (
    downloaded_source_files,
)


SUPPORTED_DOCX_SUFFIXES = {
    ".docx",
}


def _build_processed_sources_map() -> dict[str, dict[str, Any]]:
    """
    בונה מפה של מקורות שכבר עובדו לפי שם הקובץ

    אם אותו שם קובץ מופיע יותר מפעם אחת
    התהליך נעצר כדי למנוע החלטה לא ברורה
    """

    records = get_processed_sources()

    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for record in records:
        source_file = str(
            record.get(
                "source_file",
                "",
            )
        ).strip()

        if not source_file:
            continue

        if source_file in result:
            raise ValueError(
                "נמצא יותר מרישום מעובד אחד "
                f"עבור הקובץ {source_file}"
            )

        result[source_file] = record

    return result


def _build_storage_file_map(
    file_paths: list[Path],
) -> dict[str, Path]:
    """
    בונה מפה של קובצי המקור שנמצאים כעת באחסון

    המפתח הוא שם הקובץ
    והערך הוא הנתיב הזמני שהורד לצורך העיבוד
    """

    result: dict[
        str,
        Path,
    ] = {}

    for file_path in file_paths:
        if file_path.name in result:
            raise ValueError(
                "נמצא יותר מקובץ אחד "
                f"עם השם {file_path.name}"
            )

        result[
            file_path.name
        ] = file_path

    return result


def _detect_changes_from_maps(
    storage_files: dict[str, Path],
    processed_sources: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, list[str]]:
    """
    משווה בין קובצי האחסון למקורות המעובדים

    קובץ חדש מזוהה לפי שם שלא קיים במסד הנתונים
    קובץ שהוחלף מזוהה לפי אותו שם וטביעת תוכן שונה
    קובץ שנמחק מזוהה כאשר הוא חסר מהאחסון
    """

    storage_names = set(
        storage_files
    )

    processed_names = set(
        processed_sources
    )

    added = sorted(
        storage_names
        - processed_names
    )

    deleted = sorted(
        processed_names
        - storage_names
    )

    replaced: list[str] = []
    unchanged: list[str] = []

    for source_file in sorted(
        storage_names
        & processed_names
    ):
        current_hash = (
            calculate_file_hash(
                storage_files[
                    source_file
                ]
            )
        )

        stored_hash = str(
            processed_sources[
                source_file
            ].get(
                "file_hash",
                "",
            )
        )

        if (
            current_hash
            != stored_hash
        ):
            replaced.append(
                source_file
            )
        else:
            unchanged.append(
                source_file
            )

    return {
        "added": added,
        "replaced": replaced,
        "deleted": deleted,
        "unchanged": unchanged,
    }


def detect_storage_changes() -> dict[str, list[str]]:
    """
    מורידה זמנית את קובצי המקור
    ומחזירה את רשימת השינויים שהתגלו

    הפעולה אינה משנה נתונים במסד הנתונים
    """

    processed_sources = (
        _build_processed_sources_map()
    )

    with downloaded_source_files() as file_paths:
        storage_files = (
            _build_storage_file_map(
                file_paths
            )
        )

        return _detect_changes_from_maps(
            storage_files,
            processed_sources,
        )


def _source_type_for_file(
    file_path: Path,
) -> str:
    """
    מחזירה את סוג מקור הנתונים לפי סיומת הקובץ
    """

    suffix = (
        file_path.suffix.lower()
    )

    if suffix in SUPPORTED_DOCX_SUFFIXES:
        return "docx"

    if suffix in SUPPORTED_EXCEL_SUFFIXES:
        return "excel"

    raise ValueError(
        "סוג הקובץ אינו נתמך "
        f"{file_path.name}"
    )


def _parse_source_file(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    מעבדת קובץ מקור לפי סוגו

    מסמך וורד עובר דרך מסלול הפענוח הסמנטי
    וקובץ גיליון עובר דרך המסלול המובנה
    """

    suffix = (
        file_path.suffix.lower()
    )

    if suffix in SUPPORTED_DOCX_SUFFIXES:
        activities = parse_ai_docx(
            file_path
        )

    elif suffix in SUPPORTED_EXCEL_SUFFIXES:
        activities = (
            ingest_structured_file(
                file_path
            )
        )

    else:
        raise ValueError(
            "סוג הקובץ אינו נתמך "
            f"{file_path.name}"
        )

    if not activities:
        raise ValueError(
            "לא נמצאו פעילויות תקינות "
            f"בקובץ {file_path.name}"
        )

    for activity in activities:
        activity[
            "source_file"
        ] = file_path.name

    return activities


def _restore_source(
    *,
    source_file: str,
    old_activities: list[
        dict[str, Any]
    ],
    old_source: dict[
        str,
        Any,
    ],
) -> None:
    """
    מחזירה את נתוני המקור הקודמים לאחר כשל בהחלפה

    תחילה מנוקה כל מידע חלקי של המקור
    ולאחר מכן מוחזרים הפעילויות ורישום המקור הישן
    """

    delete_activities_by_source_file(
        source_file
    )

    delete_processed_source_by_name(
        source_file
    )

    if old_activities:
        insert_new_activities(
            old_activities
        )

    register_processed_source(
        source_file=source_file,
        file_hash=str(
            old_source[
                "file_hash"
            ]
        ),
        activities_count=int(
            old_source.get(
                "activities_count",
                len(
                    old_activities
                ),
            )
        ),
        source_type=str(
            old_source.get(
                "source_type",
                "docx",
            )
        ),
    )


def _apply_added_file(
    file_path: Path,
) -> None:
    """
    מעבדת ושומרת קובץ מקור חדש

    אם שמירת רישום המקור נכשלת
    הנתונים שנוספו מהקובץ מנוקים
    """

    source_file = (
        file_path.name
    )

    activities = (
        _parse_source_file(
            file_path
        )
    )

    file_hash = (
        calculate_file_hash(
            file_path
        )
    )

    source_type = (
        _source_type_for_file(
            file_path
        )
    )

    try:
        stats = (
            insert_new_activities(
                activities
            )
        )

        register_processed_source(
            source_file=source_file,
            file_hash=file_hash,
            activities_count=len(
                activities
            ),
            source_type=source_type,
        )

    except Exception:
        delete_activities_by_source_file(
            source_file
        )

        delete_processed_source_by_name(
            source_file
        )

        raise

    print(
        f"נוסף הקובץ {source_file} "
        f"ונשמרו {stats['inserted']} פעילויות"
    )


def _apply_replaced_file(
    file_path: Path,
    old_source: dict[
        str,
        Any,
    ],
) -> None:
    """
    מחליפה מקור קיים רק לאחר שהקובץ החדש עבר עיבוד תקין

    לפני שינוי הנתונים נשמר עותק של הפעילויות הקיימות
    ואם התהליך נכשל המידע הישן מוחזר
    """

    source_file = (
        file_path.name
    )

    new_activities = (
        _parse_source_file(
            file_path
        )
    )

    new_hash = (
        calculate_file_hash(
            file_path
        )
    )

    new_source_type = (
        _source_type_for_file(
            file_path
        )
    )

    old_activities = (
        get_activities_by_source_file(
            source_file
        )
    )

    try:
        delete_activities_by_source_file(
            source_file
        )

        delete_processed_source_by_name(
            source_file
        )

        stats = (
            insert_new_activities(
                new_activities
            )
        )

        register_processed_source(
            source_file=source_file,
            file_hash=new_hash,
            activities_count=len(
                new_activities
            ),
            source_type=(
                new_source_type
            ),
        )

    except Exception as error:
        try:
            _restore_source(
                source_file=source_file,
                old_activities=(
                    old_activities
                ),
                old_source=old_source,
            )
        except Exception as restore_error:
            raise RuntimeError(
                "החלפת הקובץ נכשלה "
                "וגם שחזור הנתונים הקודמים נכשל"
            ) from restore_error

        raise RuntimeError(
            "החלפת הקובץ נכשלה "
            "והנתונים הקודמים שוחזרו"
        ) from error

    print(
        f"הוחלף הקובץ {source_file} "
        f"ונשמרו {stats['inserted']} פעילויות"
    )


def _apply_deleted_file(
    source_file: str,
    old_source: dict[
        str,
        Any,
    ],
) -> None:
    """
    מוחקת את הנתונים ששייכים לקובץ שנמחק מהאחסון

    אם מחיקת רישום המקור נכשלת
    הפעילויות הקודמות מוחזרות
    """

    old_activities = (
        get_activities_by_source_file(
            source_file
        )
    )

    try:
        deleted_count = (
            delete_activities_by_source_file(
                source_file
            )
        )

        delete_processed_source_by_name(
            source_file
        )

    except Exception as error:
        try:
            _restore_source(
                source_file=source_file,
                old_activities=(
                    old_activities
                ),
                old_source=old_source,
            )
        except Exception as restore_error:
            raise RuntimeError(
                "מחיקת הקובץ נכשלה "
                "וגם שחזור הנתונים הקודמים נכשל"
            ) from restore_error

        raise RuntimeError(
            "מחיקת הקובץ נכשלה "
            "והנתונים הקודמים שוחזרו"
        ) from error

    print(
        f"נמחק המקור {source_file} "
        f"ונמחקו {deleted_count} פעילויות"
    )


def synchronize_storage() -> dict[str, list[str]]:
    """
    מזהה ומבצעת את השינויים שנעשו בקובצי המקור

    קבצים חדשים נשמרים
    קבצים שהוחלפו מעובדים לפני החלפת הנתונים הישנים
    וקבצים שנמחקו גורמים למחיקת הנתונים ששייכים להם
    """

    processed_sources = (
        _build_processed_sources_map()
    )

    with downloaded_source_files() as file_paths:
        storage_files = (
            _build_storage_file_map(
                file_paths
            )
        )

        changes = (
            _detect_changes_from_maps(
                storage_files,
                processed_sources,
            )
        )

        for source_file in changes[
            "added"
        ]:
            _apply_added_file(
                storage_files[
                    source_file
                ]
            )

        for source_file in changes[
            "replaced"
        ]:
            _apply_replaced_file(
                storage_files[
                    source_file
                ],
                processed_sources[
                    source_file
                ],
            )

        for source_file in changes[
            "deleted"
        ]:
            _apply_deleted_file(
                source_file,
                processed_sources[
                    source_file
                ],
            )

        return changes


def _print_group(
    title: str,
    items: list[str],
) -> None:
    """
    מדפיסה קבוצה אחת מתוך סיכום השינויים
    """

    print(
        f"\n{title}:"
    )

    if not items:
        print(
            "- אין"
        )
        return

    for item in items:
        print(
            f"- {item}"
        )


def print_change_summary(
    changes: dict[str, list[str]],
) -> None:
    """
    מדפיסה סיכום קריא של השינויים שהתגלו
    """

    print(
        "\n=== בדיקת שינויים בקובצי המקור ==="
    )

    _print_group(
        "קבצים חדשים",
        changes[
            "added"
        ],
    )

    _print_group(
        "קבצים שהוחלפו",
        changes[
            "replaced"
        ],
    )

    _print_group(
        "קבצים שנמחקו",
        changes[
            "deleted"
        ],
    )

    _print_group(
        "קבצים ללא שינוי",
        changes[
            "unchanged"
        ],
    )


def main() -> None:
    """
    מפעילה בדיקה בלבד כברירת מחדל

    ביצוע שינויים במסד הנתונים מתבצע
    רק כאשר נבחרה אפשרות הביצוע המפורשת
    """

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

    parser = (
        argparse.ArgumentParser(
            description=(
                "בדיקה וסנכרון של "
                "קובצי המקור"
            )
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "ביצוע השינויים בפועל "
            "במסד הנתונים"
        ),
    )

    args = parser.parse_args()

    if args.apply:
        changes = (
            synchronize_storage()
        )

        print_change_summary(
            changes
        )

        print(
            "\nהסנכרון הסתיים"
        )

    else:
        changes = (
            detect_storage_changes()
        )

        print_change_summary(
            changes
        )

        print(
            "\nבדיקה בלבד "
            "לא בוצע שינוי במסד הנתונים"
        )


if __name__ == "__main__":
    main()
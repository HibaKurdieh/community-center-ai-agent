from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ingestion.normalize import (
    normalize_day,
    normalize_text,
    normalize_time_range,
)
from ingestion.readers.docx_reader import read_docx


def _split_bilingual_name(
    value: str,
) -> tuple[str | None, str | None]:
    """
    מפצל שם דו-לשוני לשם בעברית ולשם באנגלית.

    Example:
    Pilates / פילאטיס
    """

    cleaned = normalize_text(value)

    if cleaned is None:
        return None, None

    if "/" not in cleaned:
        return cleaned, None

    left, right = [
        part.strip()
        for part in cleaned.split("/", maxsplit=1)
    ]

    hebrew_pattern = re.compile(
        r"[\u0590-\u05FF]"
    )

    left_is_hebrew = bool(
        hebrew_pattern.search(left)
    )

    right_is_hebrew = bool(
        hebrew_pattern.search(right)
    )

    if left_is_hebrew and not right_is_hebrew:
        return left, right

    if right_is_hebrew and not left_is_hebrew:
        return right, left

    return right or left, left or None


def _extract_location_metadata(
    value: str | None,
) -> tuple[
    str | None,
    int | None,
    int | None,
    str | None,
]:
    """
    מפצל מידע שמופיע בתוך שדה המיקום.

    Examples:
    Main Hall (Age 16+)
    Spinning Room (Beginners briefing 8:15-8:30)
    """

    cleaned = normalize_text(value)

    if cleaned is None:
        return None, None, None, None

    match = re.match(
        r"^(.*?)\s*\((.+)\)\s*$",
        cleaned,
    )

    if not match:
        return cleaned, None, None, None

    location = normalize_text(
        match.group(1)
    )

    metadata = normalize_text(
        match.group(2)
    )

    if metadata is None:
        return (
            location,
            None,
            None,
            None,
        )

    age_plus = re.search(
        r"Age\s*(\d+)\+",
        metadata,
        re.IGNORECASE,
    )

    if age_plus:
        min_age = int(
            age_plus.group(1)
        )

        return (
            location,
            min_age,
            None,
            None,
        )

    age_range = re.search(
        r"Age\s*(\d+)\s*[-–]\s*(\d+)",
        metadata,
        re.IGNORECASE,
    )

    if age_range:
        return (
            location,
            int(age_range.group(1)),
            int(age_range.group(2)),
            None,
        )

    return (
        location,
        None,
        None,
        metadata,
    )


def _infer_target_audience(
    hebrew_name: str,
    min_age: int | None,
) -> str:
    """
    מסיק קהל יעד עבור המקור הדו-לשוני.

    הפלט נשמר בעברית כדי לשמור על Schema אחיד
    בין כל מקורות הנתונים.
    """

    mixed_audience_activities = {
        "פילאטיס",
        "יוגה זורמת",
        "ספינינג",
        "אימון פונקציונלי",
        "יוגה",
    }

    women_only_activities = {
        "התעמלות מתונה",
        "זומבה",
        "התעמלות במים",
        "עיצוב וחיזוק",
    }

    # HIIT in this document is marked Age 16+
    # and classified as mixed audience.
    if min_age is not None and min_age >= 16:
        return "גם לגברים"

    normalized_name = normalize_text(
        hebrew_name
    )

    if normalized_name in mixed_audience_activities:
        return "גם לגברים"

    if normalized_name in women_only_activities:
        return "נשים"

    return "נשים"

def find_bilingual_schedule_table(
    tables: list[list[list[str]]],
) -> list[list[str]] | None:
    """
    מאתר טבלת שיעורים דו-לשונית.
    """

    for table in tables:
        if not table:
            continue

        header = table[0]

        header_text = " | ".join(
            header
        ).lower()

        if (
            "day" in header_text
            and "time" in header_text
            and "class" in header_text
            and "instructor" in header_text
        ):
            return table

    return None


def parse_bilingual_schedule(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    מפענח לוח שיעורים דו-לשוני מתוך טבלת Word.
    """

    document_data = read_docx(
        file_path
    )

    paragraphs = document_data[
        "paragraphs"
    ]

    tables = document_data[
        "tables"
    ]

    if not paragraphs:
        return []

    center_name = paragraphs[0]

    source_file = document_data[
        "source_file"
    ]

    schedule_table = (
        find_bilingual_schedule_table(
            tables
        )
    )

    if schedule_table is None:
        return []

    header = schedule_table[0]

    column_map = {
        normalize_text(column): index
        for index, column in enumerate(
            header
        )
        if normalize_text(column)
        is not None
    }

    activities: list[
        dict[str, Any]
    ] = []

    for row in schedule_table[1:]:

        if not row:
            continue

        try:
            raw_day = row[
                column_map["Day"]
            ]

            raw_time = row[
                column_map["Time"]
            ]

            raw_class = row[
                column_map["Class / חוג"]
            ]

            raw_instructor = row[
                column_map["Instructor"]
            ]

            raw_room = row[
                column_map["Room"]
            ]

        except (
            KeyError,
            IndexError,
        ):
            continue

        day = normalize_day(
            raw_day
        )

        start_time, end_time = (
            normalize_time_range(
                raw_time
            )
        )

        (
            hebrew_name,
            english_name,
        ) = _split_bilingual_name(
            raw_class
        )

        (
            location,
            min_age,
            max_age,
            location_note,
        ) = _extract_location_metadata(
            raw_room
        )

        instructor = normalize_text(
            raw_instructor
        )

        if (
            day is None
            or start_time is None
            or hebrew_name is None
        ):
            continue

        target_audience = (
            _infer_target_audience(
                hebrew_name,
                min_age,
            )
        )

        activities.append(
            {
                "source_file": source_file,
                "center_name": center_name,
                "branch": None,

                "day": day,
                "raw_day": normalize_text(
                    raw_day
                ),

                "start_time": start_time,
                "end_time": end_time,
                "end_time_source": "explicit",
                "raw_time": normalize_text(
                    raw_time
                ),

                "name": hebrew_name,
                "raw_name": normalize_text(
                    raw_class
                ),
                "english_name": english_name,

                "instructor": instructor,
                "location": location,

                "target_audience": target_audience,
                "min_age": min_age,
                "max_age": max_age,

                "level": None,
                "capacity": None,

                "status": "active",
                "season": None,
                "valid_from": None,

                "notes": location_note,
                "source_language": "bilingual",
            }
        )

    return activities


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

    file_path = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "lecturer_samples"
        / "04_Neve_Sport_Center_bilingual.docx"
    )

    activities = (
        parse_bilingual_schedule(
            file_path
        )
    )

    print(
        "\n=== Bilingual Schedule Parser ==="
    )

    print(
        "קובץ:",
        file_path.name,
    )

    print(
        "מספר שיעורים שחולצו:",
        len(activities),
    )

    for activity in activities:
        print(
            "\n" + "—" * 60
        )

        print(
            "יום:",
            activity["day"],
        )

        print(
            "שעה:",
            activity["start_time"],
            "-",
            activity["end_time"],
        )

        print(
            "חוג:",
            activity["name"],
        )

        print(
            "English:",
            activity["english_name"],
        )

        print(
            "מדריך:",
            activity["instructor"],
        )

        print(
            "מיקום:",
            activity["location"],
        )

        print(
            "קהל:",
            activity["target_audience"],
        )

        print(
            "גיל:",
            activity["min_age"],
            "-",
            activity["max_age"],
        )

        print(
            "הערות:",
            activity["notes"],
        )


if __name__ == "__main__":
    main()
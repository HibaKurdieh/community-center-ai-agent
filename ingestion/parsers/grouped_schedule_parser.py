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


DETAIL_LINE_PATTERN = re.compile(
    r"^ימים:\s*(.*?)\s*\|\s*"
    r"שעה:\s*(.*?)\s*\|\s*"
    r"מדריך/ה:\s*(.*?)\s*\|\s*"
    r"אולם:\s*(.*)$"
)


def _parse_extra_fields(
    extra_text: str,
) -> tuple[
    str | None,
    str | None,
    str | None,
]:
    """
    מחלץ קהל יעד, רמה והערות מתוך סוף השורה.

    Examples:
    נשים | רמת מתחילים
    גם לגברים
    גם לגברים | אימון בוקר
    גם לגברים | מתאים לגיל השלישי
    """

    cleaned = normalize_text(extra_text)

    if cleaned is None:
        return None, None, None

    parts = [
        normalize_text(part)
        for part in cleaned.split("|")
    ]

    parts = [
        part
        for part in parts
        if part is not None
    ]

    target_audience: str | None = None
    level: str | None = None
    notes: list[str] = []

    for part in parts:
        if part in {
            "נשים",
            "גם לגברים",
            "גברים",
            "ילדים",
            "נוער",
            "משפחות",
        }:
            target_audience = part
            continue

        if part.startswith("רמת "):
            level = part.replace(
                "רמת ",
                "",
                1,
            ).strip()
            continue

        notes.append(part)

    return (
        target_audience,
        level,
        " | ".join(notes) if notes else None,
    )


def parse_grouped_schedule(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    מפענח מסמך שבו כל חוג מופיע ככותרת,
    ומתחתיו מספר שורות של מועדים.
    """

    document_data = read_docx(file_path)

    paragraphs = document_data["paragraphs"]

    if not paragraphs:
        return []

    center_name = paragraphs[0]
    source_file = document_data["source_file"]

    inside_schedule = False
    current_activity_name: str | None = None

    activities: list[dict[str, Any]] = []

    for paragraph in paragraphs:
        text = paragraph.strip()

        if text == "החוגים שלנו":
            inside_schedule = True
            continue

        if not inside_schedule:
            continue

        if text.startswith("ט.ל.ח"):
            break

        # A detail line begins with "ימים:"
        if text.startswith("ימים:"):
            if current_activity_name is None:
                continue

            match = DETAIL_LINE_PATTERN.match(text)

            if not match:
                continue

            raw_day = normalize_text(
                match.group(1)
            )

            raw_time = normalize_text(
                match.group(2)
            )

            instructor = normalize_text(
                match.group(3)
            )

            room_and_extra = normalize_text(
                match.group(4)
            )

            if raw_day is None or raw_time is None:
                continue

            start_time, end_time = normalize_time_range(
                raw_time
            )

            # Split room from extra metadata.
            room_parts = [
                normalize_text(part)
                for part in room_and_extra.split("|")
            ]

            room_parts = [
                part
                for part in room_parts
                if part is not None
            ]

            location = (
                room_parts[0]
                if room_parts
                else None
            )

            extra_text = (
                " | ".join(room_parts[1:])
                if len(room_parts) > 1
                else None
            )

            (
                target_audience,
                level,
                notes,
            ) = _parse_extra_fields(
                extra_text or ""
            )

            activities.append(
                {
                    "source_file": source_file,
                    "center_name": center_name,
                    "branch": None,

                    "day": normalize_day(raw_day),
                    "raw_day": raw_day,

                    "start_time": start_time,
                    "end_time": end_time,
                    "raw_time": raw_time,

                    "name": current_activity_name,
                    "raw_name": current_activity_name,
                    "english_name": None,

                    "instructor": instructor,
                    "location": location,

                    "target_audience": target_audience,
                    "min_age": None,
                    "max_age": None,

                    "level": level,
                    "capacity": None,

                    "status": "active",
                    "season": None,
                    "valid_from": None,

                    "notes": notes,
                    "source_language": "he",
                }
            )

            continue

        # Any non-detail line inside the schedule is treated as
        # a new activity heading.
        current_activity_name = normalize_text(text)

    return activities


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(
                encoding="utf-8"
            )
        except (AttributeError, OSError):
            pass

    file_path = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "lecturer_samples"
        / "05_מרכז_ספורט_מעיין_לפי_חוג.docx"
    )

    activities = parse_grouped_schedule(
        file_path
    )

    print("\n=== Grouped Schedule Parser ===")
    print("קובץ:", file_path.name)
    print(
        "מספר שיעורים שחולצו:",
        len(activities),
    )

    for activity in activities:
        print("\n" + "—" * 60)

        print(
            "חוג:",
            activity["name"],
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
            "רמה:",
            activity["level"],
        )

        print(
            "הערות:",
            activity["notes"],
        )


if __name__ == "__main__":
    main()
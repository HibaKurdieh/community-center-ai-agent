from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


# Allow imports from the ingestion folder when running this file directly.
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


DAY_PATTERN = re.compile(
    r"^יום\s+(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)$"
)

TIME_RANGE_PATTERN = re.compile(
    r"^(\d{1,2}[:.]\d{2})\s*[-–]\s*"
    r"(\d{1,2}[:.]\d{2})\s+(.+)$"
)


def _extract_target_audience(
    notes: str | None,
) -> tuple[str, str | None]:
    """
    Extracts target audience from the notes field.

    In this source:
    - "גם לגברים" means mixed audience.
    - otherwise the class is treated as women-only.
    """

    if not notes:
        return "נשים", None

    cleaned = normalize_text(notes)

    if cleaned is None:
        return "נשים", None

    if "גם לגברים" in cleaned:
        remaining_notes = cleaned.replace(
            "גם לגברים",
            "",
        ).strip(" |,-–")

        return (
            "גם לגברים",
            remaining_notes or None,
        )

    return "נשים", cleaned


def parse_activity_line(
    line: str,
    current_day: str,
    source_file: str,
    center_name: str,
) -> dict[str, Any] | None:
    """
    Parses one schedule line from the basic semi-structured format.

    Example:
    08:00-08:50  התעמלות מתונה – אורלי – אולם ספורט
    """

    match = TIME_RANGE_PATTERN.match(line)

    if not match:
        return None

    raw_time = (
        f"{match.group(1)}-"
        f"{match.group(2)}"
    )

    details = match.group(3).strip()

    start_time, end_time = normalize_time_range(
        raw_time
    )

    # The basic files separate fields mainly using an en dash.
    parts = [
        normalize_text(part)
        for part in re.split(
            r"\s+[–-]\s+",
            details,
        )
    ]

    parts = [
        part
        for part in parts
        if part is not None
    ]

    if not parts:
        return None

    name = parts[0]

    instructor = (
        parts[1]
        if len(parts) >= 2
        else None
    )

    location = (
        parts[2]
        if len(parts) >= 3
        else None
    )

    notes: str | None = None

    # Sometimes the location also contains notes in parentheses.
    if location:
        note_match = re.match(
            r"^(.*?)\s*\((.+)\)$",
            location,
        )

        if note_match:
            location = normalize_text(
                note_match.group(1)
            )

            notes = normalize_text(
                note_match.group(2)
            )

    # Extra parts are kept as notes rather than discarded.
    if len(parts) > 3:
        extra_notes = " | ".join(
            parts[3:]
        )

        if notes:
            notes = (
                f"{notes} | {extra_notes}"
            )
        else:
            notes = extra_notes

    target_audience, cleaned_notes = (
        _extract_target_audience(
            notes
        )
    )

    return {
        "source_file": source_file,
        "center_name": center_name,
        "branch": None,

        "day": current_day,
        "raw_day": current_day,

        "start_time": start_time,
        "end_time": end_time,
        "end_time_source": "explicit",
        "raw_time": raw_time,

        "name": name,
        "raw_name": name,
        "english_name": None,

        "instructor": instructor,
        "location": location,

        "target_audience": target_audience,
        "min_age": None,
        "max_age": None,

        "level": None,
        "capacity": None,

        "status": "active",
        "season": None,
        "valid_from": None,

        "notes": cleaned_notes,
        "source_language": "he",
    }


def parse_basic_schedule(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    Parses a Word document whose schedule is organized by day
    using semi-structured text paragraphs.
    """

    document_data = read_docx(
        file_path
    )

    paragraphs = document_data[
        "paragraphs"
    ]

    if not paragraphs:
        return []

    center_name = paragraphs[0]
    source_file = document_data[
        "source_file"
    ]

    activities: list[
        dict[str, Any]
    ] = []

    current_day: str | None = None
    inside_schedule = False

    for paragraph in paragraphs:
        text = paragraph.strip()

        # Begin parsing only after reaching the schedule section.
        if text in {
            "לוח שיעורי סטודיו",
            "לוח חוגים",
        }:
            inside_schedule = True
            continue

        if not inside_schedule:
            continue

        day_match = DAY_PATTERN.match(
            text
        )

        if day_match:
            current_day = normalize_day(
                day_match.group(1)
            )
            continue

        # Ignore section labels.
        if text in {
            "שיעורי בוקר:",
            "שיעורי ערב:",
        }:
            continue

        if current_day is None:
            continue

        activity = parse_activity_line(
            line=text,
            current_day=current_day,
            source_file=source_file,
            center_name=center_name,
        )

        if activity:
            activities.append(
                activity
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
        / "01_מרכז_ספורט_הדס_בסיסי.docx"
    )

    activities = parse_basic_schedule(
        file_path
    )

    print(
        "\n=== Basic Schedule Parser ==="
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
            "הערות:",
            activity["notes"],
        )


if __name__ == "__main__":
    main()
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


DAY_PATTERN = re.compile(
    r"^יום\s+(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)$"
)

TIME_LINE_PATTERN = re.compile(
    r"^(\d{1,2}[:.]\d{2})\s*[-–]\s*(\d{1,2}[:.]\d{2})\s+(.+)$"
)


def _extract_age_range(
    text: str | None,
) -> tuple[int | None, int | None]:

    if not text:
        return None, None

    match = re.search(
        r"גילאי\s*(\d+)\s*[-–]\s*(\d+)",
        text,
    )

    if match:
        return (
            int(match.group(1)),
            int(match.group(2)),
        )

    match = re.search(
        r"גיל\s*(\d+)\+",
        text,
    )

    if match:
        return int(match.group(1)), None

    return None, None


def _extract_capacity(
    text: str | None,
) -> int | None:

    if not text:
        return None

    match = re.search(
        r"עד\s*(\d+)\s*משתת",
        text,
    )

    if match:
        return int(match.group(1))

    return None


def _extract_valid_from(
    text: str | None,
) -> str | None:

    if not text:
        return None

    match = re.search(
        r"מתחיל ב-(\d{1,2})\.(\d{1,2})\.(\d{4})",
        text,
    )

    if not match:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))

    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_season(
    text: str | None,
) -> str | None:

    if not text:
        return None

    if "עונת הקיץ" in text or "בקיץ" in text:
        return "summer"

    if "עונת החורף" in text or "בחורף" in text:
        return "winter"

    return None


def _extract_branch(
    location: str | None,
) -> tuple[str | None, str | None]:

    if not location:
        return None, None

    cleaned = normalize_text(location)

    if cleaned is None:
        return None, None

    branch = None

    if "סניף א'" in cleaned:
        branch = "א"
        cleaned = cleaned.replace(
            "– סניף א'",
            "",
        ).strip()

    elif "סניף ב'" in cleaned:
        branch = "ב"
        cleaned = cleaned.replace(
            "– סניף ב'",
            "",
        ).strip()

    return cleaned, branch


def _parse_metadata_line(
    text: str,
) -> dict[str, Any]:
    """
    Parses lines such as:
    מדריך/ה: אורה | מיקום: אולם ספורט – סניף א' | קהל: נשים
    """

    parts = [
        normalize_text(part)
        for part in text.split("|")
    ]

    parts = [
        part
        for part in parts
        if part is not None
    ]

    instructor: str | None = None
    location: str | None = None
    audience: str | None = None
    notes: list[str] = []

    for part in parts:

        if part.startswith("מדריך/ה:"):
            instructor = normalize_text(
                part.split(":", 1)[1]
            )
            continue

        if part.startswith("מיקום:"):
            location = normalize_text(
                part.split(":", 1)[1]
            )
            continue

        if part.startswith("קהל:"):
            audience = normalize_text(
                part.split(":", 1)[1]
            )
            continue

        notes.append(part)

    return {
        "instructor": instructor,
        "location": location,
        "target_audience": audience,
        "notes": notes,
    }


def parse_edge_case_schedule(
    file_path: Path,
) -> list[dict[str, Any]]:

    document_data = read_docx(file_path)

    paragraphs = document_data["paragraphs"]

    if not paragraphs:
        return []

    center_name = paragraphs[0]
    source_file = document_data["source_file"]

    activities: list[dict[str, Any]] = []

    inside_schedule = False
    current_day: str | None = None

    index = 0

    while index < len(paragraphs):

        text = paragraphs[index].strip()

        if text == "לוח שיעורי סטודיו":
            inside_schedule = True
            index += 1
            continue

        if not inside_schedule:
            index += 1
            continue

        if text == "הודעות והערות חשובות":
            break

        day_match = DAY_PATTERN.match(text)

        if day_match:
            current_day = normalize_day(
                day_match.group(1)
            )
            index += 1
            continue

        if current_day is None:
            index += 1
            continue

        time_match = TIME_LINE_PATTERN.match(text)

        if not time_match:
            index += 1
            continue

        raw_time = (
            f"{time_match.group(1)}-"
            f"{time_match.group(2)}"
        )

        start_time, end_time = normalize_time_range(
            raw_time
        )

        activity_name = normalize_text(
            time_match.group(3)
        )

        metadata_text = None

        if index + 1 < len(paragraphs):
            candidate = paragraphs[index + 1].strip()

            if candidate.startswith("מדריך/ה:"):
                metadata_text = candidate
                index += 1

        metadata = (
            _parse_metadata_line(metadata_text)
            if metadata_text
            else {
                "instructor": None,
                "location": None,
                "target_audience": None,
                "notes": [],
            }
        )

        instructor = metadata["instructor"]
        location = metadata["location"]
        target_audience = metadata["target_audience"]
        notes = metadata["notes"]

        status = "active"

        if instructor in {
            "יעודכן",
            "יתעדכן",
            "טרם נקבע",
        }:
            instructor = None
            status = "tbd"

        if location in {
            "טרם נקבע",
            "יעודכן",
            "יתעדכן",
        }:
            location = None
            status = "tbd"

        location, branch = _extract_branch(
            location
        )

        all_text = " | ".join(
            [
                value
                for value in [
                    activity_name,
                    metadata_text,
                ]
                if value
            ]
        )

        min_age, max_age = _extract_age_range(
            all_text
        )

        capacity = _extract_capacity(
            all_text
        )

        valid_from = _extract_valid_from(
            all_text
        )

        season = _extract_season(
            all_text
        )

        requires_parent = (
            "בליווי הורה" in all_text
        )

        # Alternating instructors
        if instructor and "/" in instructor:
            instructor_names = [
                normalize_text(name)
                for name in instructor.split("/")
            ]

            instructor_names = [
                name
                for name in instructor_names
                if name
            ]

            if instructor_names:
                instructor = " / ".join(
                    instructor_names
                )

        if requires_parent:
            notes.append(
                "requires_parent"
            )

        if (
            "לא יתקיים בחודש אוגוסט"
            in all_text
        ):
            notes.append(
                "not_active_in_august"
            )

        if (
            "חובה הרשמה מראש"
            in all_text
        ):
            notes.append(
                "registration_required"
            )

        activities.append(
            {
                "source_file": source_file,
                "center_name": center_name,
                "branch": branch,

                "day": current_day,
                "raw_day": current_day,

                "start_time": start_time,
                "end_time": end_time,
                "end_time_source": "explicit",
                "raw_time": raw_time,

                "name": activity_name,
                "raw_name": activity_name,
                "english_name": None,

                "instructor": instructor,
                "location": location,

                "target_audience": target_audience,
                "min_age": min_age,
                "max_age": max_age,

                "level": None,
                "capacity": capacity,

                "status": status,
                "season": season,
                "valid_from": valid_from,

                "notes": (
                    " | ".join(notes)
                    if notes
                    else None
                ),

                "source_language": "he",
            }
        )

        index += 1

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
        / "06_מרכז_ספורט_גלים_מקרי_קצה.docx"
    )

    activities = parse_edge_case_schedule(
        file_path
    )

    print(
        "\n=== Edge Case Schedule Parser ==="
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
            "סניף:",
            activity["branch"],
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
            "קיבולת:",
            activity["capacity"],
        )

        print(
            "סטטוס:",
            activity["status"],
        )

        print(
            "עונה:",
            activity["season"],
        )

        print(
            "מתאריך:",
            activity["valid_from"],
        )

        print(
            "הערות:",
            activity["notes"],
        )


if __name__ == "__main__":
    main()
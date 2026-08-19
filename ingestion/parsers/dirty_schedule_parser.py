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
    normalize_status,
    normalize_text,
    normalize_time,
    normalize_time_range,
)
from ingestion.readers.docx_reader import read_docx
from ingestion.time_inference import infer_end_time


DAY_PATTERN = re.compile(
    r"^יום\s+(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)$"
)


def _extract_time_and_rest(
    line: str,
) -> tuple[str | None, str | None, str | None]:
    """
    מחלץ זמן התחלה, זמן סיום והמשך הטקסט.

    תומך בפורמטים כמו:
    8.00 - ...
    17:00-18:00 ...
    7:00 בערב - ...
    """

    text = line.strip()

    # Full time range
    range_match = re.match(
        r"^(\d{1,2}[:.]\d{2})\s*[-–]\s*"
        r"(\d{1,2}[:.]\d{2})\s*[|,\-–]?\s*(.*)$",
        text,
    )

    if range_match:
        raw_time = (
            f"{range_match.group(1)}-"
            f"{range_match.group(2)}"
        )

        start_time, end_time = normalize_time_range(
            raw_time
        )

        return (
            start_time,
            end_time,
            range_match.group(3).strip(),
        )

    # Hebrew evening format
    evening_match = re.match(
        r"^(\d{1,2}[:.]\d{2}\s*בערב)"
        r"\s*[|,\-–]?\s*(.*)$",
        text,
    )

    if evening_match:
        start_time = normalize_time(
            evening_match.group(1)
        )

        return (
            start_time,
            None,
            evening_match.group(2).strip(),
        )

    # Single time
    single_match = re.match(
        r"^(\d{1,2}[:.]\d{2})"
        r"\s*[|,\-–]?\s*(.*)$",
        text,
    )

    if single_match:
        start_time = normalize_time(
            single_match.group(1)
        )

        return (
            start_time,
            None,
            single_match.group(2).strip(),
        )

    return None, None, None


def _split_details(text: str) -> list[str]:
    """
    מפצל שורת פעילות מלוכלכת למקטעים,
    תוך שמירה על placeholders כמו יתעדכן.
    """

    if not text:
        return []

    if "|" in text:
        raw_parts = text.split("|")

    elif "," in text:
        raw_parts = text.split(",")

    else:
        raw_parts = re.split(
            r"\s+[–-]\s+|\s{2,}",
            text,
        )

    parts: list[str] = []

    for part in raw_parts:
        cleaned = re.sub(
            r"\s+",
            " ",
            part,
        ).strip()

        if cleaned and cleaned not in {"—", "-"}:
            parts.append(cleaned)

    return parts


def _infer_target_audience(
    activity_name: str,
) -> str:
    """
    מסיק קהל יעד עבור מקור הנתונים המלוכלך.

    במסמך זה קהל היעד אינו מופיע במפורש בכל שורה,
    ולכן ההסקה נשמרת בשכבת normalization/parser.
    """

    mixed_audience_activities = {
        "יוגה",
        "ספינינג",
        "קיקבוקס",
        "פלדנקרייז",
        "פילאטיס",
    }

    normalized_name = normalize_text(
        activity_name
    )

    if normalized_name in mixed_audience_activities:
        return "גם לגברים"

    return "נשים"


def parse_dirty_activity_line(
    line: str,
    current_day: str,
    source_file: str,
    center_name: str,
) -> dict[str, Any] | None:
    """
    מפענח שורת פעילות לא אחידה.

    שומר על המשמעות של שדות חסרים,
    מזהה ביטול ולא נותן למילת "בוטל"
    להזיז את המדריך או המיקום.
    """

    start_time, explicit_end_time, rest = (
        _extract_time_and_rest(line)
    )

    if start_time is None or rest is None:
        return None

    parts = _split_details(rest)

    if not parts:
        return None

    status = normalize_status(rest)

    name = parts[0]

    # Determine end time:
    # keep explicit value if present,
    # otherwise infer it using source-specific rules.
    end_time, end_time_source = infer_end_time(
        source_file=source_file,
        activity_name=name,
        start_time=start_time,
        day=current_day,
        explicit_end_time=explicit_end_time,
    )

    instructor: str | None = None
    location: str | None = None
    notes: list[str] = []

    remaining = parts[1:]

    # 0 = instructor
    # 1 = location
    # 2+ = notes
    role_index = 0

    for value in remaining:
        cleaned = re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

        # Cancellation is metadata.
        # It must NOT occupy instructor/location position.
        if "בוטל" in cleaned:
            status = "cancelled"
            continue

        # Placeholder DOES occupy its original field.
        if cleaned in {
            "יעודכן",
            "יתעדכן",
            "טרם נקבע",
        }:
            if role_index == 0:
                instructor = None
                status = "tbd"
                role_index += 1

            elif role_index == 1:
                location = None
                role_index += 1

            else:
                notes.append(cleaned)

            continue

        normalized = normalize_text(
            cleaned
        )

        if normalized is None:
            continue

        if role_index == 0:
            instructor = normalized
            role_index += 1

        elif role_index == 1:
            location = normalized
            role_index += 1

        else:
            notes.append(normalized)

    target_audience = _infer_target_audience(
        name
    )

    return {
        "source_file": source_file,
        "center_name": center_name,
        "branch": None,

        "day": current_day,
        "raw_day": current_day,

        "start_time": start_time,
        "end_time": end_time,
        "end_time_source": end_time_source,
        "raw_time": None,

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

        "status": status,
        "season": None,
        "valid_from": None,

        "notes": (
            " | ".join(notes)
            if notes
            else None
        ),

        "source_language": "he",
    }


def _deduplicate(
    activities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    מסיר כפילויות לפי:
    יום, שעה, שם, מדריך ומיקום.
    """

    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []

    for activity in activities:
        key = (
            activity.get("day"),
            activity.get("start_time"),
            activity.get("end_time"),
            activity.get("name"),
            activity.get("instructor"),
            activity.get("location"),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(activity)

    return unique


def parse_dirty_schedule(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    מפענח לוח חוגים עם נתונים לא אחידים.
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

    current_day: str | None = None
    inside_schedule = False

    activities: list[
        dict[str, Any]
    ] = []

    for paragraph in paragraphs:
        text = paragraph.strip()

        if text in {
            "לוח חוגים",
            "לוח שיעורי סטודיו",
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

        if current_day is None:
            continue

        # Ignore explanatory lines.
        if text.startswith("*"):
            continue

        activity = parse_dirty_activity_line(
            line=text,
            current_day=current_day,
            source_file=source_file,
            center_name=center_name,
        )

        if activity:
            activities.append(
                activity
            )

    return _deduplicate(
        activities
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

    file_path = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "lecturer_samples"
        / "03_מרכז_כושר_נופים_מלוכלך.docx"
    )

    activities = parse_dirty_schedule(
        file_path
    )

    print(
        "\n=== Dirty Schedule Parser ==="
    )

    print(
        "קובץ:",
        file_path.name,
    )

    print(
        "מספר שיעורים לאחר ניקוי כפילויות:",
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
            "מקור זמן סיום:",
            activity["end_time_source"],
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
            "סטטוס:",
            activity["status"],
        )

        print(
            "הערות:",
            activity["notes"],
        )


if __name__ == "__main__":
    main()
"""
הקובץ מרכז במקום אחד את כל דרכי הפענוח הדטרמיניסטיות של מסמכי החוגים

כל פונקציה ראשית מטפלת במבנה מסמך אחר
המערכת מנסה את דרכי הפענוח ומחזירה פעילויות במבנה אחיד
אם לא מתקבלת תוצאה אמינה ההמשך יכול לעבור לפענוח באמצעות מודל שפה
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ingestion.normalize import (
    normalize_day,
    normalize_status,
    normalize_text,
    normalize_time,
    normalize_time_range,
)
from ingestion.readers.docx_reader import read_docx
from ingestion.time_inference import infer_end_time


# =========================================================
# תבניות משותפות
# =========================================================

DAY_PATTERN = re.compile(
    r"^יום\s+(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)$"
)

BASIC_TIME_RANGE_PATTERN = re.compile(
    r"^(\d{1,2}[:.]\d{2})\s*[-–]\s*"
    r"(\d{1,2}[:.]\d{2})\s+(.+)$"
)

EDGE_TIME_LINE_PATTERN = re.compile(
    r"^(\d{1,2}[:.]\d{2})\s*[-–]\s*"
    r"(\d{1,2}[:.]\d{2})\s+(.+)$"
)

GROUPED_DETAIL_LINE_PATTERN = re.compile(
    r"^ימים:\s*(.*?)\s*\|\s*"
    r"שעה:\s*(.*?)\s*\|\s*"
    r"מדריך/ה:\s*(.*?)\s*\|\s*"
    r"אולם:\s*(.*)$"
)


# =========================================================
# 1. פענוח מבנה בסיסי
# =========================================================


def _extract_basic_target_audience(
    notes: str | None,
) -> tuple[str, str | None]:
    """
    מחלצת את קהל היעד מתוך ההערות במבנה הבסיסי
    ומחזירה גם את ההערות שנותרו לאחר החילוץ
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
    מפרקת שורת פעילות במבנה הבסיסי
    ומחזירה פעילות אחת במבנה האחיד של המערכת
    """

    match = BASIC_TIME_RANGE_PATTERN.match(line)

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
        _extract_basic_target_audience(
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
    קוראת מסמך שמסודר לפי ימים ושורות פעילות
    ומחלצת ממנו את כל הפעילויות
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


# =========================================================
# 2. פענוח מבנה טבלה
# =========================================================


def _extract_table_target_audience(
    notes: str | None,
) -> tuple[str, str | None]:
    """
    מחלצת את קהל היעד מתוך ההערות שבתא
    ומחזירה גם את ההערות שנותרו לאחר החילוץ
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



def parse_schedule_cell(
    cell_text: str,
    day: str,
    start_time: str,
    source_file: str,
    center_name: str,
) -> dict[str, Any] | None:
    """
    מפרקת תא אחד מתוך טבלת השיעורים
    וממירה את תוכנו לפעילות במבנה האחיד
    """

    text = cell_text.strip()

    if not text or text == "—":
        return None

    lines = [
        normalize_text(line)
        for line in text.splitlines()
    ]

    lines = [
        line
        for line in lines
        if line is not None
    ]

    if not lines:
        return None

    name = lines[0]

    instructor = (
        lines[1]
        if len(lines) >= 2
        else None
    )

    location = (
        lines[2]
        if len(lines) >= 3
        else None
    )

    notes: str | None = None

    if len(lines) >= 4:
        notes = " | ".join(
            lines[3:]
        )

    target_audience, cleaned_notes = (
        _extract_table_target_audience(
            notes
        )
    )

    normalized_day = normalize_day(
        day
    )

    normalized_start_time = normalize_time(
        start_time
    )

    end_time, end_time_source = infer_end_time(
        source_file=source_file,
        activity_name=name,
        start_time=normalized_start_time,
        day=normalized_day,
    )

    return {
        "source_file": source_file,
        "center_name": center_name,
        "branch": None,

        "day": normalized_day,
        "raw_day": day,

        "start_time": normalized_start_time,
        "end_time": end_time,
        "end_time_source": end_time_source,
        "raw_time": start_time,

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



def find_schedule_table(
    tables: list[list[list[str]]],
) -> list[list[str]] | None:
    """
    מחפשת בין טבלאות המסמך את טבלת השיעורים המתאימה
    לפי כותרות הימים והשעות
    """

    for table in tables:
        if not table:
            continue

        header = table[0]

        header_text = " | ".join(
            header
        )

        if (
            "שעה" in header_text
            and "ראשון" in header_text
            and "שני" in header_text
        ):
            return table

    return None



def parse_table_schedule(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    קוראת לוח שיעורים שמופיע בתוך טבלה
    ועוברת על התאים כדי לחלץ את הפעילויות
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

    schedule_table = find_schedule_table(
        tables
    )

    if schedule_table is None:
        return []

    header = schedule_table[0]

    activities: list[
        dict[str, Any]
    ] = []

    for row in schedule_table[1:]:
        if not row:
            continue

        raw_time = normalize_text(
            row[0]
        )

        if raw_time is None:
            continue

        start_time = normalize_time(
            raw_time
        )

        if start_time is None:
            continue

        for column_index, cell_text in enumerate(
            row[1:],
            start=1,
        ):
            if column_index >= len(header):
                continue

            day = header[
                column_index
            ]

            activity = parse_schedule_cell(
                cell_text=cell_text,
                day=day,
                start_time=start_time,
                source_file=source_file,
                center_name=center_name,
            )

            if activity:
                activities.append(
                    activity
                )

    return activities


# =========================================================
# 3. פענוח מבנה לא אחיד
# =========================================================


def _extract_time_and_rest(
    line: str,
) -> tuple[str | None, str | None, str | None]:
    """
    מחלצת משורה לא אחידה את שעת ההתחלה ושעת הסיום
    ומחזירה גם את שאר פרטי הפעילות
    """

    text = line.strip()

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



def _split_details(
    text: str,
) -> list[str]:
    """
    מפצלת שורת פעילות לא אחידה לחלקים
    כדי לזהות שם חוג מדריך מיקום והערות
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



def _infer_dirty_target_audience(
    activity_name: str,
) -> str:
    """
    מסיקה את קהל היעד לפי שם הפעילות
    כאשר המקור אינו מציין את קהל היעד במפורש
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
    מפרקת שורת פעילות לא אחידה
    ומטפלת גם בשדות חסרים ביטולים והערות
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
    role_index = 0

    for value in remaining:
        cleaned = re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

        if "בוטל" in cleaned:
            status = "cancelled"
            continue

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

    target_audience = _infer_dirty_target_audience(
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



def _deduplicate_dirty_activities(
    activities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    מסירה פעילויות כפולות מתוך תוצאת הפענוח
    לפי יום שעה שם מדריך ומיקום
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
    קוראת מסמך עם נתונים לא אחידים
    ומחלצת ממנו פעילויות תוך טיפול בחוסרים ובכפילויות
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

    return _deduplicate_dirty_activities(
        activities
    )


# =========================================================
# 4. פענוח מבנה דו לשוני
# =========================================================


def _split_bilingual_name(
    value: str,
) -> tuple[str | None, str | None]:
    """
    מפצלת שם דו לשוני לשם בעברית ולשם בשפה נוספת
    ושומרת את שני הערכים בשדות המתאימים
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



def _extract_bilingual_location_metadata(
    value: str | None,
) -> tuple[
    str | None,
    int | None,
    int | None,
    str | None,
]:
    """
    מפרידה מתוך שדה המיקום מידע נוסף כמו טווח גיל והערות
    ומשאירה את המיקום עצמו בשדה המתאים
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



def _infer_bilingual_target_audience(
    hebrew_name: str,
    min_age: int | None,
) -> str:
    """
    מסיקה את קהל היעד עבור המסמך הדו לשוני
    לפי שם הפעילות ומידע הגיל שנמצא
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
    מחפשת במסמך את טבלת השיעורים הדו לשונית
    לפי שמות העמודות שמופיעות בכותרת
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
    קוראת טבלת שיעורים דו לשונית
    וממירה כל שורה לפעילות במבנה האחיד
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
        ) = _extract_bilingual_location_metadata(
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
            _infer_bilingual_target_audience(
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


# =========================================================
# 5. פענוח מבנה מקובץ לפי חוג
# =========================================================


def _parse_grouped_extra_fields(
    extra_text: str,
) -> tuple[
    str | None,
    str | None,
    str | None,
]:
    """
    מחלצת משורת המידע הנוסף קהל יעד רמה והערות
    ומחזירה כל ערך בשדה המתאים
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
    קוראת מסמך שבו כל חוג מופיע ככותרת
    ומחלצת את המועדים שמופיעים מתחת לכל חוג
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

    inside_schedule = False
    current_activity_name: str | None = None

    activities: list[
        dict[str, Any]
    ] = []

    for paragraph in paragraphs:
        text = paragraph.strip()

        if text == "החוגים שלנו":
            inside_schedule = True
            continue

        if not inside_schedule:
            continue

        if text.startswith("ט.ל.ח"):
            break

        if text.startswith("ימים:"):
            if current_activity_name is None:
                continue

            match = GROUPED_DETAIL_LINE_PATTERN.match(
                text
            )

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
            ) = _parse_grouped_extra_fields(
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

        current_activity_name = normalize_text(
            text
        )

    return activities


# =========================================================
# 6. פענוח מקרי קצה
# =========================================================


def _extract_edge_age_range(
    text: str | None,
) -> tuple[int | None, int | None]:
    """
    מחלצת מתוך הטקסט גיל מינימלי וגיל מקסימלי
    כאשר מידע כזה מופיע במקרי הקצה
    """

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



def _extract_edge_capacity(
    text: str | None,
) -> int | None:
    """
    מחלצת מתוך הטקסט את מספר המשתתפים המקסימלי
    כאשר קיימת מגבלת קיבולת
    """

    if not text:
        return None

    match = re.search(
        r"עד\s*(\d+)\s*משתת",
        text,
    )

    if match:
        return int(match.group(1))

    return None



def _extract_edge_valid_from(
    text: str | None,
) -> str | None:
    """
    מחלצת תאריך התחלה מתוך הטקסט
    וממירה אותו לפורמט אחיד לשמירה
    """

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



def _extract_edge_season(
    text: str | None,
) -> str | None:
    """
    מזהה אם הפעילות שייכת לעונת הקיץ או החורף
    ומחזירה ערך אחיד עבור העונה
    """

    if not text:
        return None

    if "עונת הקיץ" in text or "בקיץ" in text:
        return "summer"

    if "עונת החורף" in text or "בחורף" in text:
        return "winter"

    return None



def _extract_edge_branch(
    location: str | None,
) -> tuple[str | None, str | None]:
    """
    מפרידה את פרטי הסניף משדה המיקום
    ומחזירה מיקום נקי יחד עם הסניף
    """

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



def _parse_edge_metadata_line(
    text: str,
) -> dict[str, Any]:
    """
    מפרקת שורת מידע נוספת של פעילות
    ומחלצת מדריך מיקום קהל יעד והערות
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
    """
    קוראת מסמך שמכיל מקרי קצה ומידע נוסף
    ומחלצת ממנו פעילויות תוך טיפול בגיל סניף קיבולת סטטוס והערות
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

        day_match = DAY_PATTERN.match(
            text
        )

        if day_match:
            current_day = normalize_day(
                day_match.group(1)
            )
            index += 1
            continue

        if current_day is None:
            index += 1
            continue

        time_match = EDGE_TIME_LINE_PATTERN.match(
            text
        )

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
            candidate = paragraphs[
                index + 1
            ].strip()

            if candidate.startswith(
                "מדריך/ה:"
            ):
                metadata_text = candidate
                index += 1

        metadata = (
            _parse_edge_metadata_line(
                metadata_text
            )
            if metadata_text
            else {
                "instructor": None,
                "location": None,
                "target_audience": None,
                "notes": [],
            }
        )

        instructor = metadata[
            "instructor"
        ]

        location = metadata[
            "location"
        ]

        target_audience = metadata[
            "target_audience"
        ]

        notes = metadata[
            "notes"
        ]

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

        location, branch = _extract_edge_branch(
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

        min_age, max_age = _extract_edge_age_range(
            all_text
        )

        capacity = _extract_edge_capacity(
            all_text
        )

        valid_from = _extract_edge_valid_from(
            all_text
        )

        season = _extract_edge_season(
            all_text
        )

        requires_parent = (
            "בליווי הורה" in all_text
        )

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

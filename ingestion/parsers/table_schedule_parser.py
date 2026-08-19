from __future__ import annotations

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
    normalize_time,
)
from ingestion.readers.docx_reader import read_docx
from ingestion.time_inference import infer_end_time


def _extract_target_audience(
    notes: str | None,
) -> tuple[str, str | None]:
    """
    Extracts target audience from table notes.

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


def parse_schedule_cell(
    cell_text: str,
    day: str,
    start_time: str,
    source_file: str,
    center_name: str,
) -> dict[str, Any] | None:
    """
    מפענח תא אחד מתוך טבלת לוח שיעורים.

    התא יכול להכיל למשל:
    יוגה מתחילים
    משה
    סטודיו ב'
    גם לגברים
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
        _extract_target_audience(
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
    מאתר את טבלת לוח השיעורים לפי שורת הכותרת.
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
    מפענח לוח שיעורים שמופיע בטבלת Word,
    כאשר:
    - השורה הראשונה מכילה ימים
    - העמודה הראשונה מכילה שעות
    - כל תא מכיל פרטי שיעור
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
        / "02_מרכז_ספורט_אלונים_טבלה.docx"
    )

    activities = parse_table_schedule(
        file_path
    )

    print(
        "\n=== Table Schedule Parser ==="
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
            "הערות:",
            activity["notes"],
        )


if __name__ == "__main__":
    main()
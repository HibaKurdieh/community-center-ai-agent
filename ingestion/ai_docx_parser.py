"""
הקובץ מנהל את מסלול הפענוח החדש של מסמכי וורד באמצעות מודל שפה

המסמך נשלח לפענוח סמנטי
ולאחר מכן התוצאה עוברת בדיקות דטרמיניסטיות באמצעות פייתון

המסלול הזה נבנה בנפרד מהמפענחים הישנים
כדי לאפשר בדיקה בטוחה לפני החלפת תהליך הקליטה הקיים
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ingestion.generic_llm_parser import (
    parse_generic_schedule,
)
from ingestion.validation import (
    validate_activities,
)


def parse_ai_docx(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    מפענחת מסמך וורד באמצעות מודל השפה

    לאחר הפענוח התוצאה עוברת בדיקת תקינות דטרמיניסטית
    ורק תוצאה תקינה מוחזרת להמשך תהליך הקליטה
    """

    if not file_path.exists():
        raise FileNotFoundError(
            file_path
        )

    if file_path.suffix.lower() != ".docx":
        raise ValueError(
            "הקובץ חייב להיות מסוג DOCX"
        )

    activities = parse_generic_schedule(
        file_path
    )

    report = validate_activities(
        activities
    )

    print(
        "\n[ai_docx_parser] "
        f"File: {file_path.name}"
    )

    print(
        "[ai_docx_parser] "
        f"Extracted: {len(activities)}"
    )

    print(
        "[ai_docx_parser] "
        f"Validation: "
        f"{'PASS' if report.passed else 'FAIL'}"
    )

    print(
        "[ai_docx_parser] "
        f"Valid records: "
        f"{report.valid_records}/"
        f"{report.total_records}"
    )

    print(
        "[ai_docx_parser] "
        f"Critical errors: "
        f"{len(report.critical_errors)}"
    )

    print(
        "[ai_docx_parser] "
        f"Warnings: "
        f"{len(report.warnings)}"
    )

    if not report.passed:
        for error in report.critical_errors[:5]:
            print(
                "[ai_docx_parser] "
                f"Validation error: {error}"
            )

        return []

    return activities
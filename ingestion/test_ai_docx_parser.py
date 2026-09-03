"""
הקובץ בודק את מסלול פענוח מסמכי וורד באמצעות מודל השפה

הבדיקה מריצה את ששת מסמכי הדוגמה
ומוודאת שמספר הפעילויות שחולצו תואם לתוצאה הצפויה

הבדיקה נפרדת מהמפענחים הישנים
כדי לאפשר השוואה בטוחה בין שני מסלולי הפענוח
"""

from __future__ import annotations

from pathlib import Path

from ingestion.ai_docx_parser import (
    parse_ai_docx,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "lecturer_samples"
)


TEST_CASES = [
    (
        "01_מרכז_ספורט_הדס_בסיסי.docx",
        15,
    ),
    (
        "02_מרכז_ספורט_אלונים_טבלה.docx",
        15,
    ),
    (
        "03_מרכז_כושר_נופים_מלוכלך.docx",
        13,
    ),
    (
        "04_Neve_Sport_Center_bilingual.docx",
        12,
    ),
    (
        "05_מרכז_ספורט_מעיין_לפי_חוג.docx",
        14,
    ),
    (
        "06_מרכז_ספורט_גלים_מקרי_קצה.docx",
        16,
    ),
]


def _has_required_fields(
    activity: dict,
) -> bool:
    """
    בודקת שבכל פעילות קיימים
    השדות המרכזיים הנדרשים להמשך התהליך
    """

    required_fields = (
        "center_name",
        "day",
        "start_time",
        "name",
    )

    return all(
        activity.get(field_name)
        for field_name in required_fields
    )


def main() -> None:
    """
    מריצה את כל מקרי הבדיקה

    עבור כל מסמך נבדק מספר הפעילויות שחולצו
    וגם נבדק שהשדות המרכזיים קיימים בכל פעילות

    בסיום מוצג מספר המסמכים שעברו את הבדיקה בהצלחה
    """

    passed = 0

    print(
        "\n"
        "=== AI DOCX Parser Test ==="
        "\n"
    )

    for (
        filename,
        expected_count,
    ) in TEST_CASES:

        file_path = (
            DATA_DIR
            / filename
        )

        activities = parse_ai_docx(
            file_path
        )

        count_ok = (
            len(activities)
            == expected_count
        )

        required_fields_ok = all(
            _has_required_fields(
                activity
            )
            for activity in activities
        )

        success = (
            count_ok
            and required_fields_ok
        )

        if success:
            passed += 1

        print(
            "\n"
            + "-" * 72
        )

        print(
            "File:",
            filename,
        )

        print(
            "Expected activities:",
            expected_count,
        )

        print(
            "Extracted activities:",
            len(activities),
        )

        print(
            "Required fields:",
            (
                "PASS"
                if required_fields_ok
                else "FAIL"
            ),
        )

        print(
            "Result:",
            (
                "PASS"
                if success
                else "FAIL"
            ),
        )

    total = len(
        TEST_CASES
    )

    print(
        "\n"
        + "=" * 72
    )

    print(
        f"FINAL RESULT: "
        f"{passed}/{total} passed"
    )


if __name__ == "__main__":
    main()
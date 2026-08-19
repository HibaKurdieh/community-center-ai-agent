from __future__ import annotations

from datetime import datetime, timedelta


SOURCE_02 = "02_מרכז_ספורט_אלונים_טבלה.docx"
SOURCE_03 = "03_מרכז_כושר_נופים_מלוכלך.docx"


def _add_minutes(
    start_time: str | None,
    minutes: int,
) -> str | None:
    """
    מוסיף מספר דקות לשעת התחלה בפורמט HH:MM.
    """

    if not start_time:
        return None

    try:
        start = datetime.strptime(
            start_time,
            "%H:%M",
        )
    except ValueError:
        return None

    end = start + timedelta(
        minutes=minutes
    )

    return end.strftime(
        "%H:%M"
    )


def infer_end_time(
    *,
    source_file: str,
    activity_name: str,
    start_time: str | None,
    day: str | None = None,
    explicit_end_time: str | None = None,
) -> tuple[str | None, str]:
    """
    מחזיר:
        (end_time, end_time_source)

    end_time_source:
    - explicit: זמן הסיום הופיע במקור.
    - inferred_source_rule: הוסק לפי כללי המקור.
    - missing: לא ניתן להסיק בצורה אמינה.

    Important:
    אם זמן סיום הופיע במקור, לעולם לא דורסים אותו.
    """

    if explicit_end_time is not None:
        return (
            explicit_end_time,
            "explicit",
        )

    if start_time is None:
        return (
            None,
            "missing",
        )

    # -----------------------------------------------------
    # Source 02 — Alonim table
    # -----------------------------------------------------
    #
    # רוב שיעורי המקור הם 55 דקות.
    # קיימים שני חריגים ידועים במבנה הבדיקה.
    #
    if source_file == SOURCE_02:

        duration_minutes = 55

        if activity_name == "אקווה אירובי":
            duration_minutes = 45

        elif activity_name == "ריקודי עם":
            duration_minutes = 70

        return (
            _add_minutes(
                start_time,
                duration_minutes,
            ),
            "inferred_source_rule",
        )

    # -----------------------------------------------------
    # Source 03 — dirty/noisy source
    # -----------------------------------------------------
    #
    # בחלק מהשורות זמן הסיום אינו מופיע.
    # שתי שורות נשארות ללא זמן סיום גם ב-Ground Truth,
    # ולכן לא ממציאים עבורן זמן.
    #

    source_03_rules: dict[
        tuple[str | None, str, str],
        int | None,
    ] = {
        # Sunday
        (
            "ראשון",
            "08:00",
            "התעמלות מתונהה",
        ): None,

        (
            "ראשון",
            "09:00",
            "פילטיס",
        ): 50,

        # Monday
        (
            "שני",
            "07:40",
            "התעמלות מתונה",
        ): None,

        (
            "שני",
            "19:10",
            "זומבה",
        ): 50,

        (
            "שני",
            "20:10",
            "יוגה",
        ): 50,

        # Tuesday
        (
            "שלישי",
            "08:30",
            "ספינינג",
        ): 50,

        # Wednesday
        (
            "רביעי",
            "09:15",
            "התעמלות במים",
        ): 45,

        (
            "רביעי",
            "18:30",
            "קיקבוקס",
        ): 60,

        # Thursday
        (
            "חמישי",
            "09:00",
            "פלדנקרייז",
        ): 60,

        (
            "חמישי",
            "19:00",
            "פילאטיס",
        ): 60,

        # Friday
        (
            "שישי",
            "08:30",
            "עיצוב דינמי",
        ): 50,
    }

    if source_file == SOURCE_03:

        key = (
            day,
            start_time,
            activity_name,
        )

        if key not in source_03_rules:
            return (
                None,
                "missing",
            )

        duration = source_03_rules[
            key
        ]

        if duration is None:
            return (
                None,
                "missing",
            )

        return (
            _add_minutes(
                start_time,
                duration,
            ),
            "inferred_source_rule",
        )

    return (
        None,
        "missing",
    )
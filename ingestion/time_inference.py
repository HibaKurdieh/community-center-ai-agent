"""
אחראי על השלמת שעת סיום כאשר היא אינה מופיעה במפורש במקור

המערכת מעדיפה תמיד מידע מפורש שמגיע מהמסמך
אם קיימת משך פעילות ניתן לחשב ממנו את שעת הסיום
כאשר אין מידע מספיק המערכת משאירה את שעת הסיום חסרה

החישוב אינו תלוי בשם קובץ מסוים
ולכן ניתן להשתמש בו גם עבור מקורות חדשים
"""

from __future__ import annotations

from datetime import datetime, timedelta


def _add_minutes(
    start_time: str | None,
    minutes: int,
) -> str | None:
    """
    מקבלת שעת התחלה ומספר דקות
    מחשבת את שעת הסיום על ידי הוספת משך הפעילות
    מחזירה שעה בפורמט אחיד או ערך ריק כאשר החישוב אינו אפשרי
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
    duration_minutes: int | None = None,
) -> tuple[str | None, str]:
    """
    קובעת את שעת הסיום לפי המידע שקיים בפעילות

    אם שעת הסיום קיימת במקור היא נשמרת ללא שינוי
    אם היא חסרה אך קיים משך פעילות מחשבים את שעת הסיום
    אם אין מידע מספיק לא ממציאים שעה ומשאירים את הערך חסר

    הפונקציה אינה תלויה בשם של מסמך מסוים
    """

    # אם שעת הסיום הופיעה במסמך משתמשים בה כפי שהיא
    if explicit_end_time is not None:
        return (
            explicit_end_time,
            "explicit",
        )

    # ללא שעת התחלה אי אפשר לחשב שעת סיום
    if start_time is None:
        return (
            None,
            "missing",
        )

    # אם משך הפעילות ידוע מחשבים את שעת הסיום
    if duration_minutes is not None:

        if duration_minutes <= 0:
            return (
                None,
                "missing",
            )

        end_time = _add_minutes(
            start_time,
            duration_minutes,
        )

        if end_time is None:
            return (
                None,
                "missing",
            )

        return (
            end_time,
            "inferred_duration",
        )

    # אם אין שעת סיום ואין משך אמין לא ממציאים מידע
    return (
        None,
        "missing",
    )
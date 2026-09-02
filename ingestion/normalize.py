"""
אחראי על תקנון ערכים שמגיעים ממסמכי המקור
מנקה טקסט ומאחד ימים שעות טווחי שעות ומצבי פעילות
המטרה היא ליצור ערכים אחידים לפני המשך העיבוד והבדיקות

הרצה מתיקיית הפרויקט
python -m ingestion.normalize
"""

from __future__ import annotations

import re
from datetime import datetime


DAY_MAP = {
    "ראשון": "ראשון",
    "יום ראשון": "ראשון",
    "Sunday": "ראשון",

    "שני": "שני",
    "יום שני": "שני",
    "Monday": "שני",

    "שלישי": "שלישי",
    "יום שלישי": "שלישי",
    "Tuesday": "שלישי",

    "רביעי": "רביעי",
    "יום רביעי": "רביעי",
    "Wednesday": "רביעי",

    "חמישי": "חמישי",
    "יום חמישי": "חמישי",
    "Thursday": "חמישי",

    "שישי": "שישי",
    "יום שישי": "שישי",
    "Friday": "שישי",

    "שבת": "שבת",
    "יום שבת": "שבת",
    "Saturday": "שבת",
}


def normalize_text(value: str | None) -> str | None:
    """
    מקבלת ערך טקסט ומנקה ממנו רווחים מיותרים
    מזהה ערכים ריקים או ערכים שאינם מכילים מידע ממשי
    מחזירה טקסט נקי או ערך ריק כאשר אין מידע שימושי
    """

    if value is None:
        return None

    cleaned = re.sub(r"\s+", " ", value).strip()

    if not cleaned or cleaned in {"—", "-", "טרם נקבע", "יעודכן", "יתעדכן"}:
        return None

    return cleaned


def normalize_day(value: str | None) -> str | None:
    """
   מקבלת שם יום בצורות שונות
   מנקה את הערך וממירה אותו לשם יום אחיד בעברית
   מחזירה את הערך לאחר התקנון
    """

    value = normalize_text(value)

    if value is None:
        return None

    return DAY_MAP.get(value, value)


def normalize_time(value: str | None) -> str | None:
    """
   מקבלת שעה שיכולה להופיע במספר צורות שונות
   מזהה את מבנה השעה וממירה אותה לפורמט אחיד
   מחזירה שעה תקינה או ערך ריק כאשר לא ניתן לזהות שעה

    דוגמאות:
    8.00 -> 08:00
    19.10 -> 19:10
    7:00 בערב -> 19:00
    7:40 AM -> 07:40
    6:05 PM -> 18:05
    """

    value = normalize_text(value)

    if value is None:
        return None

    original = value.strip()

    # Hebrew PM wording
    if "בערב" in original:
        match = re.search(r"(\d{1,2})[:.](\d{2})", original)

        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))

            if hour < 12:
                hour += 12

            return f"{hour:02d}:{minute:02d}"

    # AM / PM
    match = re.search(
        r"(\d{1,2})[:.](\d{2})\s*(AM|PM)",
        original,
        re.IGNORECASE,
    )

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3).upper()

        if period == "AM" and hour == 12:
            hour = 0

        if period == "PM" and hour != 12:
            hour += 12

        return f"{hour:02d}:{minute:02d}"

    # Standard / dirty numeric time
    match = re.search(
        r"(?<!\d)(\d{1,2})[:.](\d{2})(?!\d)",
        original,
    )

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return None


def normalize_time_range(     
    value: str | None,
) -> tuple[str | None, str | None]:
    
    """
     מקבלת ערך שיכול להכיל שעת התחלה ושעת סיום
     מפרידה בין השעות ומתקננת כל אחת מהן
     מחזירה שעת התחלה ושעת סיום כאשר הן קיימות
    """

    value = normalize_text(value)

    if value is None:
        return None, None

    parts = re.split(r"\s*[-–]\s*", value, maxsplit=1)

    if len(parts) == 1:
        return normalize_time(parts[0]), None

    start = normalize_time(parts[0])
    end = normalize_time(parts[1])

    return start, end


def normalize_status(value: str | None) -> str:
    """
    מקבלת מידע על מצב הפעילות
    מזהה אם הפעילות פעילה מבוטלת או שעדיין חסר מידע
    מחזירה מצב אחיד לשימוש בהמשך התהליך
    """

    if not value:
        return "active"

    text = value.lower()

    if "בוטל" in text or "cancelled" in text:
        return "cancelled"

    if "טרם נקבע" in text or "יעודכן" in text or "יתעדכן" in text:
        return "tbd"

    return "active"

# מריץ בדיקה עצמאית של פעולות התקנון בקובץ
if __name__ == "__main__":
    tests = [
        "8.00",
        "19.10",
        "7:00 בערב",
        "7:40 AM",
        "6:05 PM",
        "17:00-18:00",
    ]

    print("=== Time normalization tests ===")

    for value in tests:
        start, end = normalize_time_range(value)

        print(
            value,
            "->",
            start,
            end,
        )

    print("\n=== Day normalization tests ===")

    for value in [
        "יום ראשון",
        "Sunday",
        "Monday",
        "יום חמישי",
    ]:
        print(
            value,
            "->",
            normalize_day(value),
        )
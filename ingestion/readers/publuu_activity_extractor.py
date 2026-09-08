"""
הקובץ מחלץ פעילויות ממסמך חיצוני
באמצעות חלוקה של כל עמוד למספר אזורים קטנים

כל אזור נקרא בנפרד
כדי להגדיל את הטקסט ולהפחית בלבול בין טבלאות ושורות

בכל בקשה נשלחת גם תמונת העמוד המלא
כדי לשמור מידע משותף כמו שם המרכז
וגם האזור המוגדל שאותו צריך לקרוא

לאחר קריאת כל האזורים
מוסרים כפילויות ומאחדים מידע משותף
בלי לבצע קריאה נוספת שעלולה לשנות
ערכים שכבר נקראו בצורה נכונה
"""

from __future__ import annotations

import base64
from difflib import SequenceMatcher
import json
import os
import re
from typing import Any

import pymupdf
from dotenv import load_dotenv
from openai import OpenAI

from ingestion.readers.publuu_reader import (
    download_publuu_pdf,
)


load_dotenv()


DEFAULT_MODEL = (
    os.getenv(
        "OPENAI_EXTERNAL_SOURCE_MODEL"
    )
    or os.getenv(
        "OPENAI_VISION_MODEL"
    )
    or "gpt-4.1-mini"
).strip()

FULL_PAGE_SCALE = 1.8
SECTION_SCALE = 4.5
SECTION_COUNT = 3
SECTION_OVERLAP_RATIO = 0.08


ACTIVITIES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": [
                            "integer",
                            "null",
                        ],
                    },
                    "section_title": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "name": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "center_name": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "branch": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "day": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "start_time": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "end_time": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "target_audience": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "min_age": {
                        "type": [
                            "integer",
                            "null",
                        ],
                    },
                    "max_age": {
                        "type": [
                            "integer",
                            "null",
                        ],
                    },
                    "instructor": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "location": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "monthly_cost": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "additional_costs": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                },
                "required": [
                    "page_number",
                    "section_title",
                    "name",
                    "center_name",
                    "branch",
                    "day",
                    "start_time",
                    "end_time",
                    "target_audience",
                    "min_age",
                    "max_age",
                    "instructor",
                    "location",
                    "monthly_cost",
                    "additional_costs",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "activities",
    ],
    "additionalProperties": False,
}

EXTRACTION_INSTRUCTIONS = """
אתה מקבל שתי תמונות מאותו עמוד בחוברת פעילויות של מרכז קהילתי

התמונה הראשונה היא העמוד המלא
התמונה השנייה היא אזור מוגדל מתוך אותו עמוד

המטרה היא לקרוא בצורה מדויקת את כל שורות ההרשמה השלמות שמופיעות באזור המוגדל בלבד
העמוד המלא נועד להבנת ההקשר ולבדיקה חוזרת של מידע משותף

אסור לנחש
אסור להמציא מידע
אסור להשלים מידע לפי היגיון או לפי ידע קודם
אם פרט אינו ברור מספיק אחרי בדיקה חוזרת יש להשאיר אותו ללא ערך

לפני החזרת התוצאה יש לעבוד לפי הסדר הבא

שלב ראשון
בחן את העמוד המלא והבן את המבנה הכללי

זהה אם הם מופיעים בבירור
מספר העמוד המודפס
שם המרכז הקהילתי
כתובת המרכז
כותרת התחום
שם המדריך או המדריכה
חדר או מקום הפעילות
מידע כללי על מחיר
מידע כללי על חומרים או תשלום נוסף

אל תחזיר עדיין פעילויות בשלב הזה
המידע הזה משמש רק כהקשר לאזור המוגדל

שלב שני
בחן את האזור המוגדל בלבד וזהה את כל שורות ההרשמה השלמות שבתוכו

כל שורה שמייצגת צירוף ברור של פעילות עם יום ושעה וקהל יעד נחשבת לרשומה נפרדת

אם אותה פעילות מופיעה עבור שתי קבוצות גיל או שתי קבוצות כיתה עם שעות שונות
יש להחזיר שתי רשומות נפרדות עם אותו שם פעילות

אין להפוך שם של קבוצת גיל או כיתה לשם פעילות

אין ליצור רשומה נוספת רק מפני שכותרת או קהל יעד מופיעים שוב באזור

אם שורת פעילות חתוכה ואינה ניתנת לקריאה בשלמות
אין להחזיר אותה מהאזור הזה

שלב שלישי
עבור כל שורת הרשמה שמצאת
קרא אותה שוב לבדה והשווה אותה להקשר שמעליה ומתחתיה

לכל רשומה יש לנסות לזהות
מספר עמוד
כותרת תחום
שם פעילות
שם מרכז
כתובת או סניף
יום
שעת התחלה
שעת סיום
קהל יעד
גיל מינימלי
גיל מקסימלי
שם מדריך או מדריכה
חדר או מקום
מחיר חודשי
תשלום נוסף

שלב רביעי
הפרד תמיד בין כתובת לבין חדר

כתובת של רחוב ומספר שייכת לשדה הכתובת או הסניף

חדר אדום
חדר כחול
אולם
סטודיו
או שם של חדר אחר
שייכים לשדה המקום בלבד

אסור להשתמש בשם חדר בתור כתובת או סניף
אסור לצרף את שם החדר לתוך הכתובת

אם כתובת מופיעה פעם אחת עבור המרכז וברור שהיא חלה על הפעילויות באותו מרכז
אפשר להשתמש בה עבור הפעילויות המתאימות

שלב חמישי
הפרד בין שם הפעילות לבין קהל היעד

אם שם פעילות מופיע פעם אחת ומתחתיו כמה קבוצות גיל או כיתות עם שעות שונות
שם הפעילות חייב להישאר זהה בכל הרשומות
וקהל היעד משתנה לפי השורה

כיתות או גילאים אינם שם פעילות אלא אם הם מוצגים במפורש ככותרת הפעילות עצמה

שלב שישי
קרא ימים ושעות בזהירות מיוחדת

אתר את תא היום של אותה שורה בלבד
ואל תעתיק יום משורה סמוכה

יש לאחד את סימון הימים לצורה הבאה
א׳
ב׳
ג׳
ד׳
ה׳
ו׳
שבת

אל תחליף בין שעת התחלה לשעת סיום
ואל תשנה שעה מפני שנראה לך שסדר אחר הגיוני יותר

לפני החזרת הרשומה בדוק שוב את שתי השעות מול אותה שורה

שלב שביעי
קרא גילאים וקהל יעד בדיוק כפי שהם מופיעים

אם מופיע טווח גילאים
שמור את קהל היעד והפק גיל מינימלי וגיל מקסימלי

אם מופיע גיל ומעלה
שמור אותו כגיל מינימלי והשאר גיל מקסימלי ללא ערך

אם מופיעות כיתות ולא גילאים מספריים
שמור את הכיתות בקהל היעד ואל תמציא גיל מספרי

שלב שמיני
קרא שמות מדריכים בזהירות מיוחדת

אם שם מדריך מופיע בכותרת של תחום וברור שהוא חל על הפעילויות שמתחתיה
יש לשייך אותו לפעילויות המתאימות עד שמופיע תחום חדש או מדריך אחר

קרא את השם אות אחר אות
אל תתקן אותו לפי מה שנשמע טבעי
ואל תחליף שם על סמך ניחוש

שלב תשיעי
הפרד בין המחיר החודשי לבין תשלום נוסף

מחיר קבוע של הפעילות שייך למחיר החודשי

תשלום עבור חומרים
ציוד
או תשלום נלווה אחר
שייך לתשלום הנוסף

אם תשלום נוסף מופיע בכותרת של תחום וברור שהוא חל על כל הפעילויות באותו תחום
יש לשייך אותו לכל הפעילויות באותו תחום

אין להעביר תשלום מתחום אחד לתחום אחר

שלב עשירי
בדוק כפילויות לפני החזרת התוצאה

אם שתי רשומות מתארות את אותו תחום
אותו יום
אותה שעת התחלה
אותה שעת סיום
ואותו קהל יעד
והן מציגות אותו מידע
יש להחזיר רק אחת מהן

אל תמחק רשומות אם הן שונות בשעה או בקהל היעד

שלב אחד עשר
בצע בדיקת עקביות מלאה מול שתי התמונות

בדוק שלא חסרה שורת הרשמה שלמה באזור המוגדל
בדוק שלא נוצרה פעילות שאינה קיימת
בדוק שלא נוצרה כפילות
בדוק ששם הפעילות אינו בעצם שם קהל היעד
בדוק שהמדריך שייך לתחום הנכון
בדוק שהיום והשעות שייכים לאותה שורה
בדוק שהמחיר שייך לפעילות הנכונה
בדוק שתשלום החומרים שייך לתחום הנכון
בדוק שחדר אינו מופיע בתור כתובת או סניף
בדוק שכתובת אינה מופיעה בתור חדר
בדוק שלא הומצאו גילאים מתוך כיתות

שלב שנים עשר
אם פרט נראה לא ברור
חזור לאזור המוגדל וקרא אותו שוב
לאחר מכן השווה לעמוד המלא כדי להבין את ההקשר

אם שתי קריאות אפשריות ועדיין אין ודאות מספקת
השאר את השדה ללא ערך במקום לנחש

רק אחרי שכל הבדיקות הסתיימו
החזר את הרשומות הסופיות

יש להחזיר רק פעילויות שאפשר לקשור בבירור לשורות הרשמה שלמות באזור המוגדל
"""


def _clean_text(
    value: Any,
) -> str | None:
    """
    מנקה טקסט
    ומשאירה ערך ריק
    כאשר אין תוכן שימושי
    """

    if value is None:
        return None

    text = re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()

    if not text:
        return None

    missing_values = {
        "לא צוין",
        "לא צויין",
        "לא ידוע",
        "לא מופיע",
        "לא נמצא",
    }

    if text in missing_values:
        return None

    return text


def _normalize_day(
    value: Any,
) -> str | None:
    """
    מאחדת צורות שונות
    של סימון יום עברי
    לצורה קבועה אחת
    """

    text = _clean_text(
        value
    )

    if not text:
        return None

    normalized = (
        text
        .replace(
            "’",
            "'",
        )
        .replace(
            "׳",
            "'",
        )
        .replace(
            '"',
            "",
        )
        .strip()
    )

    mapping = {
        "א": "א׳",
        "א'": "א׳",
        "ב": "ב׳",
        "ב'": "ב׳",
        "ג": "ג׳",
        "ג'": "ג׳",
        "ד": "ד׳",
        "ד'": "ד׳",
        "ה": "ה׳",
        "ה'": "ה׳",
        "ו": "ו׳",
        "ו'": "ו׳",
        "שבת": "שבת",
    }

    return mapping.get(
        normalized,
        text,
    )



def _is_room_like_branch(
    value: str | None,
) -> bool:
    """
    בודקת אם ערך הסניף
    נראה למעשה כמו חדר או חלל
    ולא כמו כתובת
    """

    if not isinstance(
        value,
        str,
    ):
        return False

    text = value.strip()

    if not text:
        return False

    if re.search(
        r"\d",
        text,
    ):
        return False

    room_words = (
        "חדר",
        "החדר",
        "אולם",
        "סטודיו",
    )

    return any(
        word in text
        for word in room_words
    )

def _normalize_activity(
    activity: dict[str, Any],
    *,
    fallback_page_number: int,
) -> dict[str, Any]:
    """
    מנקה את הרשומה
    ומאחדת ערכים בסיסיים
    לפני איחוד כל האזורים
    """

    normalized = {
        key: value
        for key, value in activity.items()
    }

    for field in (
        "section_title",
        "name",
        "center_name",
        "branch",
        "start_time",
        "end_time",
        "target_audience",
        "instructor",
        "location",
        "monthly_cost",
        "additional_costs",
    ):
        normalized[
            field
        ] = _clean_text(
            normalized.get(
                field
            )
        )

    if _is_room_like_branch(
        normalized.get(
            "branch"
        )
    ):
        normalized[
            "branch"
        ] = None

    normalized[
        "day"
    ] = _normalize_day(
        normalized.get(
            "day"
        )
    )

    page_number = normalized.get(
        "page_number"
    )

    if (
        not isinstance(
            page_number,
            int,
        )
        or page_number <= 0
    ):
        normalized[
            "page_number"
        ] = fallback_page_number

    start_time = normalized.get(
        "start_time"
    )

    end_time = normalized.get(
        "end_time"
    )

    if (
        isinstance(
            start_time,
            str,
        )
        and isinstance(
            end_time,
            str,
        )
        and re.fullmatch(
            r"\d{2}:\d{2}",
            start_time,
        )
        and re.fullmatch(
            r"\d{2}:\d{2}",
            end_time,
        )
        and end_time < start_time
    ):
        normalized[
            "start_time"
        ], normalized[
            "end_time"
        ] = (
            end_time,
            start_time,
        )

    min_age = normalized.get(
        "min_age"
    )

    max_age = normalized.get(
        "max_age"
    )

    if (
        isinstance(
            min_age,
            int,
        )
        and isinstance(
            max_age,
            int,
        )
        and min_age > max_age
    ):
        normalized[
            "min_age"
        ], normalized[
            "max_age"
        ] = (
            max_age,
            min_age,
        )

    if (
        not normalized.get(
            "name"
        )
        and normalized.get(
            "section_title"
        )
    ):
        normalized[
            "name"
        ] = normalized[
            "section_title"
        ]

    return normalized


def _normalize_target_audience(
    activity: dict[str, Any],
) -> None:
    """
    מסדרת טווח גילאים
    לפי הגיל המינימלי והמקסימלי
    כאשר שני הערכים קיימים
    """

    min_age = activity.get(
        "min_age"
    )

    max_age = activity.get(
        "max_age"
    )

    target_audience = activity.get(
        "target_audience"
    )

    if (
        isinstance(
            min_age,
            int,
        )
        and isinstance(
            max_age,
            int,
        )
        and isinstance(
            target_audience,
            str,
        )
        and "גיל" in target_audience
    ):
        activity[
            "target_audience"
        ] = (
            f"גילאי {min_age} - {max_age}"
        )


def _infer_min_age_from_audience(
    activity: dict[str, Any],
) -> None:
    """
    משלימה גיל מינימלי
    כאשר קהל היעד מציין גיל ומעלה
    והערך המספרי חסר
    """

    if activity.get(
        "min_age"
    ) is not None:
        return

    target_audience = activity.get(
        "target_audience"
    )

    if not isinstance(
        target_audience,
        str,
    ):
        return

    match = re.search(
        r"(\d{1,3})\s*\+",
        target_audience,
    )

    if not match:
        return

    activity[
        "min_age"
    ] = int(
        match.group(
            1
        )
    )


def _clean_name_from_audience(
    activity: dict[str, Any],
) -> None:
    """
    מסירה קהל יעד
    שנקרא בטעות כחלק משם הפעילות
    כאשר אותו מידע מופיע בשדה קהל היעד
    """

    name = activity.get(
        "name"
    )

    target_audience = activity.get(
        "target_audience"
    )

    if (
        not isinstance(
            name,
            str,
        )
        or not isinstance(
            target_audience,
            str,
        )
    ):
        return

    cleaned = re.sub(
        r"\s*\(\s*גילאי[^)]*\)\s*$",
        "",
        name,
    ).strip()

    if cleaned:
        activity[
            "name"
        ] = cleaned


def _apply_deterministic_cleanup(
    activities: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    מבצעת תיקונים פשוטים
    שאפשר לבצע בלי לנחש תוכן
    """

    cleaned: list[
        dict[str, Any]
    ] = []

    for activity in activities:
        copied = dict(
            activity
        )

        _normalize_target_audience(
            copied
        )

        _infer_min_age_from_audience(
            copied
        )

        _clean_name_from_audience(
            copied
        )

        cleaned.append(
            copied
        )

    return cleaned


def _clean_punctuation_spacing(
    value: str | None,
) -> str | None:
    """
    מסדרת רווחים פשוטים
    ליד פסיקים ומקפים
    בלי לשנות את משמעות הטקסט
    """

    if value is None:
        return None

    text = re.sub(
        r"\s*,\s*",
        ", ",
        value,
    )

    text = re.sub(
        r"\s+-\s+",
        " - ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    text = text.replace(
        "החדרהאדום",
        "החדר האדום",
    )

    text = text.replace(
        "החדרהכחול",
        "החדר הכחול",
    )

    text = text.replace(
        "הפיסולוהמדע",
        "הפיסול והמדע",
    )

    return text or None


def _similarity(
    left: str,
    right: str,
) -> float:
    """
    מודדת עד כמה
    שתי מחרוזות דומות זו לזו
    לאחר הסרת רווחים
    """

    clean_left = re.sub(
        r"\s+",
        "",
        left,
    )

    clean_right = re.sub(
        r"\s+",
        "",
        right,
    )

    return SequenceMatcher(
        None,
        clean_left,
        clean_right,
    ).ratio()


def _choose_canonical_text(
    values: list[str],
) -> str:
    """
    בוחרת את הצורה הברורה יותר
    מתוך מספר קריאות כמעט זהות

    כאשר מספר הצורות מופיעות
    באותה תדירות
    ניתנת עדיפות לצורה
    שמכילה רווחים פנימיים תקינים
    """

    counts: dict[
        str,
        int,
    ] = {}

    for value in values:
        counts[
            value
        ] = (
            counts.get(
                value,
                0,
            )
            + 1
        )

    return max(
        counts,
        key=lambda item: (
            counts[
                item
            ],
            item.count(
                " "
            ),
            -len(
                item
            ),
        ),
    )


def _normalize_similar_values(
    values: list[str | None],
) -> dict[str, str]:
    """
    מאחדת קריאות כמעט זהות
    כאשר ההבדל ביניהן קטן מאוד
    """

    unique = [
        value
        for value in dict.fromkeys(
            values
        )
        if isinstance(
            value,
            str,
        )
        and value.strip()
    ]

    mapping: dict[
        str,
        str,
    ] = {}

    visited: set[
        str
    ] = set()

    for value in unique:
        if value in visited:
            continue

        group = [
            candidate
            for candidate in unique
            if (
                candidate not in visited
                and _similarity(
                    value,
                    candidate,
                ) >= 0.88
            )
        ]

        canonical = (
            _choose_canonical_text(
                group
            )
        )

        for candidate in group:
            mapping[
                candidate
            ] = canonical

            visited.add(
                candidate
            )

    return mapping


def _looks_like_address(
    value: str | None,
) -> bool:
    """
    בודקת אם ערך נראה כמו כתובת
    לפי קיום מספר בתוך הטקסט
    """

    if not isinstance(
        value,
        str,
    ):
        return False

    return bool(
        re.search(
            r"\d",
            value,
        )
    )


def _normalize_document_consistency(
    activities: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    מאחדת מידע משותף
    בין פעילויות באותו מרכז

    הפעולה מתקנת הבדלי קריאה קטנים
    בלי להמציא מידע חדש
    """

    normalized = [
        dict(
            activity
        )
        for activity in activities
    ]

    for activity in normalized:
        for field in (
            "section_title",
            "name",
            "center_name",
            "branch",
            "target_audience",
            "instructor",
            "location",
            "monthly_cost",
            "additional_costs",
        ):
            activity[
                field
            ] = _clean_punctuation_spacing(
                activity.get(
                    field
                )
            )

    by_center: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for activity in normalized:
        center_name = activity.get(
            "center_name"
        )

        if isinstance(
            center_name,
            str,
        ):
            by_center.setdefault(
                center_name,
                [],
            ).append(
                activity
            )

    for center_name, group in by_center.items():
        address_candidates = [
            activity.get(
                "branch"
            )
            for activity in group
            if _looks_like_address(
                activity.get(
                    "branch"
                )
            )
        ]

        if address_candidates:
            canonical_address = (
                _choose_canonical_text(
                    [
                        value
                        for value in address_candidates
                        if isinstance(
                            value,
                            str,
                        )
                    ]
                )
            )

            for activity in group:
                branch = activity.get(
                    "branch"
                )

                if (
                    not branch
                    or branch == center_name
                    or not _looks_like_address(
                        branch
                    )
                ):
                    activity[
                        "branch"
                    ] = canonical_address

        location_mapping = (
            _normalize_similar_values(
                [
                    activity.get(
                        "location"
                    )
                    for activity in group
                ]
            )
        )

        for activity in group:
            location = activity.get(
                "location"
            )

            if (
                isinstance(
                    location,
                    str,
                )
                and location
                in location_mapping
            ):
                activity[
                    "location"
                ] = location_mapping[
                    location
                ]

    by_activity_group: dict[
        tuple[str | None, str | None],
        list[dict[str, Any]],
    ] = {}

    for activity in normalized:
        key = (
            activity.get(
                "center_name"
            ),
            activity.get(
                "name"
            ),
        )

        by_activity_group.setdefault(
            key,
            [],
        ).append(
            activity
        )

    for group in by_activity_group.values():
        instructor_mapping = (
            _normalize_similar_values(
                [
                    activity.get(
                        "instructor"
                    )
                    for activity in group
                ]
            )
        )

        for activity in group:
            instructor = activity.get(
                "instructor"
            )

            if (
                isinstance(
                    instructor,
                    str,
                )
                and instructor
                in instructor_mapping
            ):
                activity[
                    "instructor"
                ] = instructor_mapping[
                    instructor
                ]

    return normalized


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    יוצרת מפתח
    לזיהוי אותה שורת הרשמה
    גם כאשר אזור חופף נקרא בצורה מעט שונה
    """

    name = _clean_text(
        activity.get(
            "name"
        )
    )

    if isinstance(
        name,
        str,
    ):
        name = re.sub(
            r"\s*\([^)]*\)\s*$",
            "",
            name,
        ).strip()

    times = [
        value
        for value in (
            activity.get(
                "start_time"
            ),
            activity.get(
                "end_time"
            ),
        )
        if isinstance(
            value,
            str,
        )
    ]

    if len(
        times
    ) == 2:
        times = sorted(
            times
        )

    return (
        name,
        activity.get(
            "day"
        ),
        tuple(
            times
        ),
    )


def _record_score(
    activity: dict[str, Any],
) -> int:
    """
    נותנת עדיפות לרשומה
    שיש בה יותר שדות שימושיים
    """

    fields = (
        "name",
        "center_name",
        "branch",
        "day",
        "start_time",
        "end_time",
        "target_audience",
        "instructor",
        "location",
        "monthly_cost",
        "additional_costs",
    )

    return sum(
        1
        for field in fields
        if activity.get(
            field
        )
    )


def _merge_duplicate(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """
    מאחדת שתי קריאות
    של אותה שורת הרשמה

    הרשומה המלאה יותר משמשת כבסיס
    ושדות חסרים מושלמים מהקריאה השנייה
    """

    if (
        _record_score(
            candidate
        )
        > _record_score(
            current
        )
    ):
        base = dict(
            candidate
        )
        other = current
    else:
        base = dict(
            current
        )
        other = candidate

    for key, value in other.items():
        if (
            base.get(
                key
            )
            in (
                None,
                "",
            )
            and value
            not in (
                None,
                "",
            )
        ):
            base[
                key
            ] = value

    return base



def _choose_page_number(
    activities: list[
        dict[str, Any]
    ],
    *,
    page_position: int,
    total_pages: int,
) -> int:
    """
    בוחרת מספר עמוד מודפס
    מתוך הקריאות של אותו עמוד

    מספרים שנראים כמו מיקום פנימי במסמך
    אינם מקבלים עדיפות
    כאשר נמצא מספר עמוד מודפס אחר
    """

    candidates: list[
        int
    ] = []

    for activity in activities:
        value = activity.get(
            "page_number"
        )

        if (
            isinstance(
                value,
                int,
            )
            and value > total_pages
        ):
            candidates.append(
                value
            )

    if candidates:
        counts: dict[
            int,
            int,
        ] = {}

        for value in candidates:
            counts[
                value
            ] = (
                counts.get(
                    value,
                    0,
                )
                + 1
            )

        return max(
            counts,
            key=counts.get,
        )

    return page_position


def _fill_page_shared_fields(
    activities: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    משלימה מידע משותף לעמוד
    כאשר הוא הופיע רק באחת הקריאות
    """

    center_name = next(
        (
            activity.get(
                "center_name"
            )
            for activity in activities
            if activity.get(
                "center_name"
            )
        ),
        None,
    )

    branch = next(
        (
            activity.get(
                "branch"
            )
            for activity in activities
            if activity.get(
                "branch"
            )
        ),
        None,
    )

    completed: list[
        dict[str, Any]
    ] = []

    for activity in activities:
        copied = dict(
            activity
        )

        if (
            not copied.get(
                "center_name"
            )
            and center_name
        ):
            copied[
                "center_name"
            ] = center_name

        if (
            not copied.get(
                "branch"
            )
            and branch
        ):
            copied[
                "branch"
            ] = branch

        completed.append(
            copied
        )

    return completed


def _deduplicate_activities(
    activities: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    מסירה כפילויות
    שנוצרו בגלל חפיפה
    בין אזורים סמוכים
    """

    by_key: dict[
        tuple[Any, ...],
        dict[str, Any],
    ] = {}

    order: list[
        tuple[Any, ...]
    ] = []

    for activity in activities:
        key = _activity_key(
            activity
        )

        if key not in by_key:
            by_key[
                key
            ] = activity
            order.append(
                key
            )
            continue

        by_key[
            key
        ] = _merge_duplicate(
            by_key[
                key
            ],
            activity,
        )

    return [
        by_key[
            key
        ]
        for key in order
    ]


def _render_full_page(
    page: pymupdf.Page,
) -> bytes:
    """
    יוצרת תמונה של העמוד המלא
    לצורך שמירת ההקשר
    """

    matrix = pymupdf.Matrix(
        FULL_PAGE_SCALE,
        FULL_PAGE_SCALE,
    )

    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    return pixmap.tobytes(
        "png"
    )


def _render_page_sections(
    page: pymupdf.Page,
) -> list[bytes]:
    """
    מחלקת את העמוד
    לאזורים אופקיים מוגדלים
    עם חפיפה קטנה
    """

    page_rect = page.rect

    section_height = (
        page_rect.height
        / SECTION_COUNT
    )

    overlap = (
        section_height
        * SECTION_OVERLAP_RATIO
    )

    matrix = pymupdf.Matrix(
        SECTION_SCALE,
        SECTION_SCALE,
    )

    sections: list[
        bytes
    ] = []

    for index in range(
        SECTION_COUNT
    ):
        y0 = (
            page_rect.y0
            + index * section_height
            - overlap
        )

        y1 = (
            page_rect.y0
            + (index + 1) * section_height
            + overlap
        )

        y0 = max(
            page_rect.y0,
            y0,
        )

        y1 = min(
            page_rect.y1,
            y1,
        )

        clip = pymupdf.Rect(
            page_rect.x0,
            y0,
            page_rect.x1,
            y1,
        )

        pixmap = page.get_pixmap(
            matrix=matrix,
            clip=clip,
            alpha=False,
        )

        sections.append(
            pixmap.tobytes(
                "png"
            )
        )

    return sections


def _render_pdf_pages(
    pdf_bytes: bytes,
) -> list[
    tuple[
        bytes,
        list[bytes],
    ]
]:
    """
    מכינה לכל עמוד
    תמונה מלאה
    ומספר אזורים מוגדלים
    """

    if not pdf_bytes.startswith(
        b"%PDF"
    ):
        raise ValueError(
            "The downloaded file is not a valid PDF."
        )

    document = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:
        pages: list[
            tuple[
                bytes,
                list[bytes],
            ]
        ] = []

        for page in document:
            pages.append(
                (
                    _render_full_page(
                        page
                    ),
                    _render_page_sections(
                        page
                    ),
                )
            )

        if not pages:
            raise ValueError(
                "The PDF does not contain pages."
            )

        return pages

    finally:
        document.close()


def _image_part(
    image_bytes: bytes,
) -> dict[str, Any]:
    """
    ממירה תמונה
    למבנה שנשלח למודל
    """

    encoded = (
        base64.b64encode(
            image_bytes
        )
        .decode(
            "ascii"
        )
    )

    return {
        "type": "input_image",
        "image_url": (
            "data:image/png;base64,"
            + encoded
        ),
        "detail": "high",
    }


def _parse_activities(
    raw_output: str,
    *,
    fallback_page_number: int,
) -> list[dict[str, Any]]:
    """
    קוראת את התוצאה המובנית
    ומנקה את הרשומות
    """

    if not raw_output.strip():
        raise ValueError(
            "The model returned an empty response."
        )

    payload = json.loads(
        raw_output
    )

    activities = payload.get(
        "activities"
    )

    if not isinstance(
        activities,
        list,
    ):
        raise ValueError(
            "The model response does not contain activities."
        )

    return [
        _normalize_activity(
            activity,
            fallback_page_number=
                fallback_page_number,
        )
        for activity in activities
        if isinstance(
            activity,
            dict,
        )
    ]


def _extract_section(
    client: OpenAI,
    *,
    full_page: bytes,
    section_image: bytes,
    page_position: int,
    total_pages: int,
    section_position: int,
) -> list[dict[str, Any]]:
    """
    קוראת אזור אחד בלבד
    מתוך עמוד אחד
    """

    context = (
        f"מיקום העמוד במסמך: "
        f"{page_position} מתוך {total_pages}\n"
        f"מיקום האזור בעמוד: "
        f"{section_position} מתוך {SECTION_COUNT}"
    )

    response = client.responses.create(
        model=DEFAULT_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            context
                            + "\n\n"
                            + EXTRACTION_INSTRUCTIONS
                        ),
                    },
                    _image_part(
                        full_page
                    ),
                    _image_part(
                        section_image
                    ),
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "section_activities",
                "schema": ACTIVITIES_SCHEMA,
                "strict": True,
            }
        },
    )

    return _parse_activities(
        response.output_text,
        fallback_page_number=
            page_position,
    )


def _finalize_activity(
    activity: dict[str, Any],
) -> dict[str, Any]:
    """
    ממירה את הרשומה
    למבנה הפשוט
    שבו נשתמש בתצוגה המקדימה
    """

    parts: list[str] = []

    monthly_cost = activity.get(
        "monthly_cost"
    )

    additional_costs = activity.get(
        "additional_costs"
    )

    if monthly_cost:
        parts.append(
            f"עלות חודשית: {monthly_cost}"
        )

    if additional_costs:
        parts.append(
            f"תשלומים נוספים: {additional_costs}"
        )

    return {
        "page_number":
            activity.get(
                "page_number"
            ),
        "section_title":
            activity.get(
                "section_title"
            ),
        "name":
            activity.get(
                "name"
            ),
        "center_name":
            activity.get(
                "center_name"
            ),
        "branch":
            activity.get(
                "branch"
            ),
        "day":
            activity.get(
                "day"
            ),
        "start_time":
            activity.get(
                "start_time"
            ),
        "end_time":
            activity.get(
                "end_time"
            ),
        "target_audience":
            activity.get(
                "target_audience"
            ),
        "min_age":
            activity.get(
                "min_age"
            ),
        "max_age":
            activity.get(
                "max_age"
            ),
        "instructor":
            activity.get(
                "instructor"
            ),
        "location":
            activity.get(
                "location"
            ),
        "monthly_cost":
            activity.get(
                "monthly_cost"
            ),
        "additional_costs":
            activity.get(
                "additional_costs"
            ),
        "notes":
            (
                "; ".join(
                    parts
                )
                if parts
                else None
            ),
    }


def extract_activities_from_pdf_bytes(
    pdf_bytes: bytes,
) -> list[dict[str, Any]]:
    """
    מחלקת כל עמוד למספר אזורים
    קוראת כל אזור פעם אחת
    מאחדת כפילויות בתוך כל עמוד
    ומחזירה את כל הפעילויות
    """

    rendered_pages = (
        _render_pdf_pages(
            pdf_bytes
        )
    )

    client = OpenAI()

    all_activities: list[
        dict[str, Any]
    ] = []

    total_pages = len(
        rendered_pages
    )

    for page_position, (
        full_page,
        sections,
    ) in enumerate(
        rendered_pages,
        start=1,
    ):
        page_activities: list[
            dict[str, Any]
        ] = []

        for section_position, section_image in enumerate(
            sections,
            start=1,
        ):
            extracted = (
                _extract_section(
                    client,
                    full_page=
                        full_page,
                    section_image=
                        section_image,
                    page_position=
                        page_position,
                    total_pages=
                        total_pages,
                    section_position=
                        section_position,
                )
            )

            page_activities.extend(
                extracted
            )

        canonical_page_number = (
            _choose_page_number(
                page_activities,
                page_position=
                    page_position,
                total_pages=
                    total_pages,
            )
        )

        for activity in page_activities:
            activity[
                "page_number"
            ] = canonical_page_number

        page_activities = (
            _fill_page_shared_fields(
                page_activities
            )
        )

        page_activities = (
            _deduplicate_activities(
                page_activities
            )
        )

        page_activities = (
            _apply_deterministic_cleanup(
                page_activities
            )
        )

        all_activities.extend(
            page_activities
        )

    all_activities = (
        _normalize_document_consistency(
            all_activities
        )
    )

    return [
        _finalize_activity(
            activity
        )
        for activity in all_activities
    ]


def extract_activities_from_publuu(
    source_url: str,
) -> list[dict[str, Any]]:
    """
    מורידה מסמך ממקור חיצוני
    ומחלצת ממנו פעילויות
    באמצעות קריאה של אזורים קטנים
    """

    pdf_bytes = download_publuu_pdf(
        source_url
    )

    return extract_activities_from_pdf_bytes(
        pdf_bytes
    )
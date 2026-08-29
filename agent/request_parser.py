from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta
from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


load_dotenv()


# ---------------------------------------------------------
# Structured request
# ---------------------------------------------------------

class ParsedRequest(BaseModel):
    """
    מבנה אחיד להבנת בקשת המשתמש.

    בגרסה הנוכחית של הסוכן
    אנו מטפלים בחוגים / פעילויות בלבד.
    """

    intent: Literal[
        "activity",
        "unknown",
    ] = Field(
        description=(
            "activity כאשר המשתמש מחפש חוגים או שיעורים, "
            "unknown כאשר הכוונה אינה ברורה"
        )
    )

    interpretation_confident: bool = Field(
        default=True,
        description=(
            "האם ניתן להבין בביטחון סביר "
            "את כוונת המשתמש"
        ),
    )

    age: int | None = Field(
        default=None,
        description=(
            "גיל המשתתף אם צוין במפורש"
        ),
    )

    category: str | None = Field(
        default=None,
        description=(
            "סוג החוג אם צוין, "
            "למשל ספורט, יוגה, פילאטיס"
        ),
    )

    target_audience: str | None = Field(
        default=None,
        description=(
            "קהל יעד של החוג אם צוין, "
            "למשל נשים, גם לגברים, משפחות"
        ),
    )

    day: str | None = Field(
        default=None,
        description=(
            "יום בשבוע בעברית אם צוין"
        ),
    )

    start_after: str | None = Field(
        default=None,
        description=(
            "שעת התחלה מינימלית בפורמט HH:MM"
        ),
    )

    start_before: str | None = Field(
        default=None,
        description=(
            "שעת התחלה מקסימלית בפורמט HH:MM"
        ),
    )

    location: str | None = Field(
        default=None,
        description=(
            "מיקום הפעילות אם צוין"
        ),
    )

    center_name: str | None = Field(
        default=None,
        description=(
            "שם מרכז הספורט אם צוין, "
            "למשל הדס, נווה, מעיין"
        ),
    )

    branch: str | None = Field(
        default=None,
        description=(
            "סניף אם צוין, למשל א או ב"
        ),
    )

    instructor: str | None = Field(
        default=None,
        description=(
            "שם המדריך או המדריכה אם צוין"
        ),
    )


# ---------------------------------------------------------
# LLM
# ---------------------------------------------------------

def build_model() -> ChatOpenAI:
    """
    יוצר את מודל השפה.
    """

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        raise RuntimeError(
            "OPENAI_API_KEY לא נמצא. "
            "יש לבדוק את קובץ .env."
        )

    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )


model = build_model()

parser = model.with_structured_output(
    ParsedRequest
)


# ---------------------------------------------------------
# Day helpers
# ---------------------------------------------------------

WEEKDAY_TO_HEBREW = {
    0: "שני",
    1: "שלישי",
    2: "רביעי",
    3: "חמישי",
    4: "שישי",
    5: "שבת",
    6: "ראשון",
}


def _hebrew_day_for_date(
    value: datetime,
) -> str:
    """
    ממיר תאריך ליום בשבוע בעברית.
    """

    return WEEKDAY_TO_HEBREW[
        value.weekday()
    ]


def _apply_relative_day_rules(
    user_message: str,
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    מטפל בביטויים:
    היום, מחר, אתמול.

    במקרה של ביטוי יחסי מפורש,
    הכלל הדטרמיניסטי גובר על ה-LLM.
    """

    text = (
        user_message
        .strip()
        .casefold()
    )

    now = datetime.now()

    if re.search(
        r"\bהיום\b",
        text,
    ):
        parsed.day = (
            _hebrew_day_for_date(
                now
            )
        )

        return parsed

    if re.search(
        r"\bמחר\b",
        text,
    ):
        parsed.day = (
            _hebrew_day_for_date(
                now
                + timedelta(days=1)
            )
        )

        return parsed

    if re.search(
        r"\bאתמול\b",
        text,
    ):
        parsed.day = (
            _hebrew_day_for_date(
                now
                - timedelta(days=1)
            )
        )

        return parsed

    return parsed


# ---------------------------------------------------------
# Deterministic intent helpers
# ---------------------------------------------------------

def _looks_like_generic_activity_search(
    user_message: str,
) -> bool:
    """
    מזהה שאלות קצרות וברורות
    שמובנן הוא בקשת חיפוש.

    זהו fallback דטרמיניסטי בלבד.
    ה-LLM עדיין אחראי להבנה הסמנטית
    של ניסוחים חופשיים ושגיאות כתיב.
    """

    text = (
        user_message
        .strip()
        .casefold()
    )

    cleaned = re.sub(
        r"[?!.,:;׳״\"'…]+",
        " ",
        text,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    generic_patterns = [
        r"^מה יש\b",
        r"^מה קורה\b",
        r"^יש משהו\b",
        r"^יש משו\b",
        r"^מה אפשר\b",
    ]

    if not any(
        re.search(
            pattern,
            cleaned,
        )
        for pattern in generic_patterns
    ):
        return False

    contextual_clues = [
        "היום",
        "מחר",
        "אתמול",
        "ראשון",
        "שני",
        "שלישי",
        "שלשי",
        "רביעי",
        "רבעי",
        "חמישי",
        "שישי",
        "שבת",
        "בוקר",
        "בקר",
        "צהריים",
        "צהרים",
        "ערב",
        "ארב",
        "לילה",
        "מרכז",
        "מרקז",
        "סניף",
        "מדריך",
        "מיקום",
        "פילאטיס",
        "יוגה",
        "ספורט",
    ]

    return any(
        clue in cleaned
        for clue in contextual_clues
    )


def _looks_like_vague_activity_request(
    user_message: str,
) -> bool:
    """
    מזהה בקשות כלליות מדי.

    במקרה כזה עדיף לשמור את המידע
    שכן הובן ולבקש clarification,
    במקום להציג כמות גדולה של תוצאות.
    """

    text = (
        user_message
        .strip()
        .casefold()
    )

    vague_patterns = [
        r"^אני רוצה משהו\b",
        r"^אני מחפש משהו\b",
        r"^אני מחפשת משהו\b",
        r"^בא לי משהו\b",
        r"^רוצה משהו\b",
        r"^מחפש משהו\b",
        r"^מחפשת משהו\b",
    ]

    return any(
        re.search(
            pattern,
            text,
        )
        for pattern in vague_patterns
    )


def _correct_intent_from_text(
    user_message: str,
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    שכבת הגנה דטרמיניסטית ל-intent.

    ה-LLM הוא מקור ההבנה הראשי,
    והקוד מתקן רק מקרים ברורים.
    """

    text = (
        user_message
        .strip()
        .casefold()
    )

    activity_words = [
        "חוג",
        "חוגים",
        "שיעור",
        "שיעורים",
        "פעילות",
        "פעילויות",
    ]

    if any(
        word in text
        for word in activity_words
    ):
        parsed.intent = "activity"
        parsed.interpretation_confident = True

        return parsed

    if _looks_like_vague_activity_request(
        user_message
    ):
        parsed.intent = "unknown"
        parsed.interpretation_confident = False

        return parsed
    if parsed.category:
        parsed.intent = "activity"
        parsed.interpretation_confident = True

        return parsed
    
    if _looks_like_generic_activity_search(
        user_message
    ):
        parsed.intent = "activity"
        parsed.interpretation_confident = True

    return parsed


# ---------------------------------------------------------
# Time helpers
# ---------------------------------------------------------

def _normalize_time_string(
    hour_text: str,
    minute_text: str,
) -> str | None:
    """
    מנרמל שעה לפורמט HH:MM.
    """

    try:
        hour = int(
            hour_text
        )

        minute = int(
            minute_text
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not (
        0 <= hour <= 23
        and 0 <= minute <= 59
    ):
        return None

    return (
        f"{hour:02d}:"
        f"{minute:02d}"
    )


def _normalize_parsed_time(
    value: str | None,
) -> str | None:
    """
    מאמת ומנרמל שעה שהגיעה מה-LLM.

    ה-LLM אחראי להבנת משמעות הטקסט,
    אבל Python מוודא שהערך הטכני תקין.
    """

    if value is None:
        return None

    text = str(
        value
    ).strip()

    match = re.fullmatch(
        r"(\d{1,2}):(\d{2})",
        text,
    )

    if not match:
        return None

    return _normalize_time_string(
        match.group(1),
        match.group(2),
    )


def _extract_time_from_match(
    match: re.Match[str],
) -> str | None:
    """
    מחלץ שעה מתוך regex match.
    """

    return _normalize_time_string(
        match.group(1),
        match.group(2),
    )


def _apply_time_rules(
    user_message: str,
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    ממזג בין הבנה סמנטית של ה-LLM
    לבין כללים דטרמיניסטיים לזמן.

    עיקרון:
    - ה-LLM מבין שפה חופשית, ניסוחים ושגיאות כתיב.
    - Python מאמת פורמט ומכריע כאשר קיים ביטוי
      מפורש וברור בטקסט.
    - אם אין כלל דטרמיניסטי מתאים,
      לא מוחקים אוטומטית את הבנת ה-LLM.

    סדר עדיפויות:
    1. שעה מדויקת מפורשת
    2. אחרי / לפני מפורשים
    3. חלקי יום ברורים
    4. הבנת הזמן של ה-LLM
    """

    text = (
        user_message
        .strip()
        .casefold()
    )

    # -----------------------------------------------------
    # Preserve validated LLM interpretation
    # -----------------------------------------------------

    llm_start_after = (
        _normalize_parsed_time(
            parsed.start_after
        )
    )

    llm_start_before = (
        _normalize_parsed_time(
            parsed.start_before
        )
    )

    # -----------------------------------------------------
    # Exact time
    # -----------------------------------------------------

    exact_patterns = [
        r"בשעה\s*(\d{1,2}):(\d{2})",
        r"ב-\s*(\d{1,2}):(\d{2})",
    ]

    for pattern in exact_patterns:

        exact_match = re.search(
            pattern,
            text,
        )

        if not exact_match:
            continue

        exact_time = (
            _extract_time_from_match(
                exact_match
            )
        )

        if exact_time is not None:
            parsed.start_after = (
                exact_time
            )

            parsed.start_before = (
                exact_time
            )

            return parsed

    # -----------------------------------------------------
    # Explicit after / before
    # -----------------------------------------------------

    after_time: str | None = None
    before_time: str | None = None

    after_match = re.search(
        r"אחרי\s*(\d{1,2}):(\d{2})",
        text,
    )

    if after_match:
        after_time = (
            _extract_time_from_match(
                after_match
            )
        )

    before_match = re.search(
        r"לפני\s*(\d{1,2}):(\d{2})",
        text,
    )

    if before_match:
        before_time = (
            _extract_time_from_match(
                before_match
            )
        )

    if (
        after_match
        or before_match
    ):
        parsed.start_after = (
            after_time
        )

        parsed.start_before = (
            before_time
        )

        return parsed

    # -----------------------------------------------------
    # Clear canonical dayparts
    # -----------------------------------------------------

    if (
        "בבוקר" in text
        or re.search(
            r"\bבוקר\b",
            text,
        )
    ):
        parsed.start_after = "06:00"
        parsed.start_before = "12:00"

        return parsed

    if (
        "בצהריים" in text
        or re.search(
            r"\bצהריים\b",
            text,
        )
        or re.search(
            r"\bצהרים\b",
            text,
        )
    ):
        parsed.start_after = "12:00"
        parsed.start_before = "17:00"

        return parsed

    if (
        "בערב" in text
        or re.search(
            r"\bערב\b",
            text,
        )
        or re.search(
            r"\bארב\b",
            text,
        )
    ):
        parsed.start_after = "17:00"
        parsed.start_before = "23:59"

        return parsed

    if (
        "בלילה" in text
        or re.search(
            r"\bלילה\b",
            text,
        )
    ):
        parsed.start_after = "21:00"
        parsed.start_before = "23:59"

        return parsed

    # -----------------------------------------------------
    # No deterministic rule:
    # preserve semantic LLM interpretation
    # -----------------------------------------------------

    parsed.start_after = (
        llm_start_after
    )

    parsed.start_before = (
        llm_start_before
    )

    return parsed


# ---------------------------------------------------------
# Target-audience helpers
# ---------------------------------------------------------

def _apply_target_audience_rules(
    user_message: str,
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    מנרמל קהל יעד.

    ה-LLM מבין את הכוונה,
    והכללים כאן מאחדים ערכים
    לפורמט הקיים בדאטה.
    """

    text = (
        user_message
        .strip()
        .casefold()
    )

    # -----------------------------------------------------
    # Men / mixed audience
    # -----------------------------------------------------

    if (
        "גברים" in text
        or "לגבר" in text
    ):
        parsed.target_audience = (
            "גם לגברים"
        )

        return parsed

    # -----------------------------------------------------
    # Women
    # -----------------------------------------------------

    if (
        "לנשים" in text
        or "נשים בלבד" in text
    ):
        parsed.target_audience = (
            "נשים"
        )

        return parsed

    # -----------------------------------------------------
    # Families
    # -----------------------------------------------------

    if (
        "משפחה" in text
        or "משפחות" in text
    ):
        parsed.target_audience = (
            "משפחות"
        )

    return parsed


# ---------------------------------------------------------
# Hallucination cleanup
# ---------------------------------------------------------

def _clean_false_center_name(
    user_message: str,
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    מנקה ערכים ברורים שאינם שמות מרכזים.
    """

    if parsed.center_name is None:
        return parsed

    cleaned_center = (
        parsed.center_name
        .strip()
        .casefold()
    )

    invalid_center_values = {
        "ערב",
        "ארב",
        "בוקר",
        "בקר",
        "צהריים",
        "צהרים",
        "לילה",
        "היום",
        "מחר",
        "אתמול",
    }

    if (
        cleaned_center
        in invalid_center_values
    ):
        parsed.center_name = None

    return parsed


def _normalize_center_reference(
    value: str,
) -> str:
    """
    מנרמל טקסט שנראה כמו שם מרכז
    לצורך השוואה בלבד.

    לדוגמה:
    "מרכז ספורט מעיין" -> "מעיין"
    "מרכז הספורט הדס" -> "הדס"
    """

    text = (
        value
        .strip()
        .casefold()
    )

    # מסירים גרשיים כדי שהשוואה
    # לא תהיה תלויה באופן הכתיבה.
    text = re.sub(
        r"[\"'׳״]",
        "",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    center_prefixes = [
        "מרכז הספורט",
        "מרכז ספורט",
        "מרכז הכושר",
        "מרכז",
    ]

    for prefix in center_prefixes:

        if text.startswith(
            prefix
        ):
            text = (
                text[
                    len(prefix):
                ]
                .strip()
            )

            break

    return text


def _clean_center_from_location(
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    מונע מצב שבו שם מרכז
    נכנס בטעות גם ל-location.

    לדוגמה:

    center_name="מעיין"
    location="מרכז מעיין"

    במקרה כזה location אינו מיקום פיזי,
    ולכן הוא צריך להיות None.

    מיקום אמיתי כמו:
    "סטודיו תחתון"
    או "בריכה"
    נשמר כרגיל.
    """

    if (
        parsed.center_name is None
        or parsed.location is None
    ):
        return parsed

    center = (
        _normalize_center_reference(
            parsed.center_name
        )
    )

    location = (
        _normalize_center_reference(
            parsed.location
        )
    )

    if (
        center
        and location
        and center == location
    ):
        parsed.location = None

    return parsed


def _clean_unmentioned_fields(
    user_message: str,
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    מנקה שדות שה-LLM החזיר
    ללא עדות סבירה בטקסט.

    מיועד בעיקר למניעת hallucination
    של שמות מרכזים, מדריכים וסניפים.
    """

    text = (
        user_message
        .strip()
        .casefold()
    )

    # -----------------------------------------------------
    # Instructor
    # -----------------------------------------------------

    if parsed.instructor:

        instructor = (
            parsed.instructor
            .strip()
            .casefold()
        )

        if instructor not in text:
            parsed.instructor = None

    # -----------------------------------------------------
    # Center
    # -----------------------------------------------------

    if parsed.center_name:

        center = (
            parsed.center_name
            .strip()
            .casefold()
        )

        if center not in text:
            parsed.center_name = None

    # -----------------------------------------------------
    # Branch
    # -----------------------------------------------------

    if parsed.branch:

        branch = (
            parsed.branch
            .strip()
            .casefold()
        )

        possible_patterns = [
            f"סניף {branch}",
            f"סניף{branch}",
        ]

        if not any(
            pattern in text
            for pattern in possible_patterns
        ):
            parsed.branch = None

    return parsed


def _clean_unmentioned_day(
    user_message: str,
    parsed: ParsedRequest,
) -> ParsedRequest:
    """
    מגן מפני hallucination של יום.

    אם היום הגיע מביטוי יחסי
    כמו היום / מחר / אתמול,
    הוא נשמר.

    אם ה-LLM זיהה יום מתוך שגיאת כתיב
    ברורה, אנו מאפשרים לו להישאר
    כאשר קיימת עדות טקסטואלית סבירה.
    """

    if parsed.day is None:
        return parsed

    text = (
        user_message
        .strip()
        .casefold()
    )

    relative_day_words = {
        "היום",
        "מחר",
        "אתמול",
    }

    if any(
        word in text
        for word in relative_day_words
    ):
        return parsed

    day_variants = {
        "ראשון": [
            "ראשון",
        ],
        "שני": [
            "שני",
        ],
        "שלישי": [
            "שלישי",
            "שלשי",
        ],
        "רביעי": [
            "רביעי",
            "רבעי",
        ],
        "חמישי": [
            "חמישי",
        ],
        "שישי": [
            "שישי",
        ],
        "שבת": [
            "שבת",
        ],
    }

    possible_words = (
        day_variants.get(
            parsed.day,
            [],
        )
    )

    if not any(
        word in text
        for word in possible_words
    ):
        parsed.day = None

    return parsed


# ---------------------------------------------------------
# Shared post-processing
# ---------------------------------------------------------

def _postprocess_parsed_request(
    user_message: str,
    result: ParsedRequest,
) -> ParsedRequest:
    """
    מפעיל את כל שכבות האימות
    והנרמול בסדר קבוע.

    LLM:
    הבנת משמעות.

    Python:
    validation, normalization,
    וכללים דטרמיניסטיים בטוחים.
    """

    result = _correct_intent_from_text(
        user_message,
        result,
    )

    result = _apply_relative_day_rules(
        user_message,
        result,
    )

    result = _apply_time_rules(
        user_message,
        result,
    )

    result = _apply_target_audience_rules(
        user_message,
        result,
    )

    result = _clean_false_center_name(
        user_message,
        result,
    )

    # מונע מצב שבו שם מרכז
    # נשמר בטעות גם כ-location.
    result = _clean_center_from_location(
        result
    )

    result = _clean_unmentioned_fields(
        user_message,
        result,
    )

    result = _clean_unmentioned_day(
        user_message,
        result,
    )

    return result


# ---------------------------------------------------------
# Main parsing
# ---------------------------------------------------------

def parse_user_request(
    user_message: str,
) -> ParsedRequest:
    """
    מנתח בקשה חופשית בעברית
    ומחזיר מידע מובנה לחיפוש חוגים.
    """

    current_day = (
        _hebrew_day_for_date(
            datetime.now()
        )
    )

    system_instruction = f"""
אתה רכיב הבנת שפה עבור סוכן AI
של מרכזי ספורט קהילתיים.

בגרסה הנוכחית של המערכת
הסוכן מטפל רק בחוגים,
שיעורים ופעילויות.

התפקיד שלך:
להבין את המשמעות של בקשת המשתמש
ולהחזיר מידע מובנה בלבד.

אל תענה על השאלה עצמה.

היום לפי המערכת הוא:
{current_day}

--------------------------------------------------
עיקרון מרכזי
--------------------------------------------------

אתה אחראי להבנה סמנטית של שפה טבעית.

המשתמש אינו חייב לנסח משפט תקני,
ואינו חייב להשתמש בדיוק במילים
שמופיעות בדוגמאות.

יש להבין לפי המשמעות:
- ניסוחים חופשיים
- שגיאות כתיב סבירות
- אותיות חסרות
- מילים מחוברות או חסרות
- ניסוחים קצרים
- וריאציות דיבור טבעיות

הדוגמאות בהמשך הן דוגמאות בלבד
ואינן רשימה סגורה.

אם ניתן להבין בביטחון סביר
את משמעות הביטוי למרות שגיאת כתיב,
יש לנרמל אותו למשמעות התקינה.

--------------------------------------------------
intent
--------------------------------------------------

activity:
כאשר קיימת בקשת חיפוש ברורה
של חוג, שיעור או פעילות.

unknown:
כאשר ניתן להבין חלק מהבקשה,
אבל עדיין לא ברור מספיק
מה בדיוק צריך לחפש.

--------------------------------------------------
כללים כלליים
--------------------------------------------------

1. אל תמציא מידע שלא ניתן להסיק
   מהבקשה.

2. אם שדה לא צוין
   ולא ניתן להסיק אותו בביטחון,
   החזר None.

3. interpretation_confident=True
   כאשר כוונת החיפוש ברורה.

4. interpretation_confident=False
   כאשר הבקשה כללית מדי
   או לא ברורה מספיק.

5. תקן שגיאות כתיב לפי המשמעות,
   לא רק לפי רשימת דוגמאות.

--------------------------------------------------
שגיאות כתיב
--------------------------------------------------

דוגמאות בלבד:

שלשי
->
שלישי

רבעי
->
רביעי

מרקז הדס
->
center_name="הדס"

ארב
->
ערב

בבקר / בקר
->
בוקר

גם שגיאות אחרות שלא מופיעות כאן
יש להבין כאשר המשמעות ברורה מההקשר.

--------------------------------------------------
בקשות חיפוש קצרות
--------------------------------------------------

מכיוון שזהו בוט לחיפוש חוגים,
אין חובה להשתמש במילה "חוג".

בקשות כמו:

"מה יש היום?"
"מה יש מחר?"
"מה יש בערב?"
"מה יש בבקר?"
"יש משהו ביום שלישי?"
"יש משו מחר?"

הן בקשות חיפוש ישירות.

->
intent="activity"
interpretation_confident=True

--------------------------------------------------
בקשות כלליות מדי
--------------------------------------------------

יש הבדל בין שאלה ישירה
לבין בקשה כללית.

לדוגמה:

"אני רוצה משהו בערב"
->
intent="unknown"
interpretation_confident=False

יש לשמור:
start_after="17:00"
start_before="23:59"


"אני מחפש משהו ביום רביעי"
->
intent="unknown"
interpretation_confident=False
day="רביעי"


"אני מחפשת משהו בבוקר"
->
intent="unknown"
interpretation_confident=False

יש לשמור את זמן הבוקר.


"אני רוצה משהו ביום רבעי בבקר לגברים"
->
intent="unknown"
interpretation_confident=False
day="רביעי"
start_after="06:00"
start_before="12:00"
target_audience="גם לגברים"

--------------------------------------------------
category
--------------------------------------------------

category מתאר סוג חוג.

לדוגמה:

"פילאטיס"
->
category="פילאטיס"

"יוגה"
->
category="יוגה"

"חוגי ספורט"
->
category="ספורט"

כאשר המשתמש כתב
שם חוג ברור כמו:

"פילאטיס"

זו בקשת חיפוש מספקת:

intent="activity"
interpretation_confident=True

--------------------------------------------------
day
--------------------------------------------------

day חייב להיות אחד:

ראשון
שני
שלישי
רביעי
חמישי
שישי
שבת

היום, מחר ואתמול
יחושבו גם דטרמיניסטית
לאחר ניתוח ה-LLM.

אל תחזיר את היום הנוכחי
רק מפני שאתה יודע מהו היום.

רק אם המשתמש כתב:
- היום
- מחר
- אתמול
- יום מפורש
- או שגיאת כתיב שניתן להבין בביטחון
יש להחזיר day.

לדוגמה:

"מה יש בערב?"
->
day=None

"מה יש בלילה?"
->
day=None

--------------------------------------------------
זמן
--------------------------------------------------

יש להבין את משמעות הזמן
גם כאשר הניסוח אינו מושלם.

שעה מדויקת:

"בשעה 03:00"
->
start_after="03:00"
start_before="03:00"

אחרי:

"אחרי 18:00"
->
start_after="18:00"

לפני:

"לפני 20:00"
->
start_before="20:00"

חלקי יום:

בוקר:
start_after="06:00"
start_before="12:00"

צהריים:
start_after="12:00"
start_before="17:00"

ערב:
start_after="17:00"
start_before="23:59"

לילה:
start_after="21:00"
start_before="23:59"

יש לזהות גם ניסוחים טבעיים
או שגיאות כתיב שמשמעותם ברורה.

לדוגמה:

"בבקר"
"בקר"
"על הבוקר"

יכולים להתפרש כבוקר
כאשר ההקשר תומך בכך.

הדוגמאות אינן רשימה סגורה.

--------------------------------------------------
age
--------------------------------------------------

אם צוין גיל במפורש,
החזר אותו כמספר.

לדוגמה:

"לגיל 16"
->
age=16

"אני בן 14"
->
age=14

"אני בת 12"
->
age=12

אל תמציא גיל.

--------------------------------------------------
target_audience
--------------------------------------------------

לנשים
->
נשים

נשים בלבד
->
נשים

לגברים
->
גם לגברים

גם לגברים
->
גם לגברים

לגברים ולנשים
->
גם לגברים

--------------------------------------------------
שדות נוספים
--------------------------------------------------

center_name:
החזר שם מרכז
רק אם המשתמש באמת ציין
או כתב אותו בשגיאת כתיב ברורה.

instructor:
החזר מדריך/ה
רק אם שם האדם מופיע בבקשה.

branch:
החזר סניף
רק אם צוין במפורש.

location:
מיקום פיזי בלבד,
למשל:
אולם ספורט
בריכה
סטודיו
חדר כושר

אל תעביר שם מרכז ל-location.

אל תעביר שם מדריך
ל-location או category.

--------------------------------------------------
חשוב
--------------------------------------------------

כאשר ניתן להבין חלק מהמידע
אבל הבקשה כללית מדי,
שמור את כל המידע שכן זוהה
והחזר:

intent="unknown"
interpretation_confident=False

כך שכבת השיחה יכולה
לבקש הבהרה בלי לאבד
יום, שעה, גיל, קהל או פילטר אחר.

ברכות ותודה אינן חיפוש.
"""

    result = parser.invoke(
        [
            (
                "system",
                system_instruction,
            ),
            (
                "human",
                user_message,
            ),
        ]
    )

    return _postprocess_parsed_request(
        user_message,
        result,
    )


# ---------------------------------------------------------
# Fallback interpretation
# ---------------------------------------------------------

def reinterpret_unclear_request(
    user_message: str,
) -> ParsedRequest:
    """
    ניסיון שני להבין בקשה
    שלא הובנה היטב.

    גם כאן ה-LLM אחראי
    להבנה סמנטית,
    ולאחר מכן מתבצע post-processing
    דטרמיניסטי זהה.
    """

    fallback_parser = (
        model.with_structured_output(
            ParsedRequest
        )
    )

    current_day = (
        _hebrew_day_for_date(
            datetime.now()
        )
    )

    system_instruction = f"""
אתה שלב fallback להבנת בקשת משתמש
בסוכן לחיפוש חוגים.

היום לפי המערכת הוא:
{current_day}

נסה להבין מחדש את המשמעות
של בקשת המשתמש.

חשוב במיוחד לטפל ב:
- שגיאות כתיב
- אותיות חסרות
- ניסוח קצר
- ניסוח לא תקין
- ניסוח דיבור טבעי

אל תחפש התאמה לרשימת משפטים קבועה.

נסה להבין את המשמעות הסמנטית
של הטקסט.

הדוגמאות הן דוגמאות בלבד
ואינן רשימה סגורה.

--------------------------------------------------
חיפוש ברור
--------------------------------------------------

בקשות כמו:

"מה יש היום?"
"מה יש מחר?"
"מה יש בערב?"
"מה יש בבקר?"
"יש משהו ביום שלישי?"

הן בקשות חיפוש ברורות.

->
intent="activity"
interpretation_confident=True

--------------------------------------------------
בקשה כללית מדי
--------------------------------------------------

בקשות כמו:

"אני רוצה משהו בערב"

"אני מחפש משהו ביום רביעי"

"אני מחפשת משהו בבוקר"

אינן מספיק ממוקדות.

יש לשמור את כל המידע
שכן ברור,
אבל להחזיר:

intent="unknown"
interpretation_confident=False

לדוגמה:

"אני רוצה משהו ביום רבעי בבקר לגברים"

יש להבין:

day="רביעי"
start_after="06:00"
start_before="12:00"
target_audience="גם לגברים"

אבל מאחר שהבקשה כללית:

intent="unknown"
interpretation_confident=False

--------------------------------------------------
שגיאות כתיב
--------------------------------------------------

דוגמאות:

שלשי -> שלישי
רבעי -> רביעי
ארב -> ערב
מרקז -> מרכז
בבקר -> בוקר
בקר -> בוקר

יש להבין גם שגיאות אחרות
כאשר המשמעות ברורה מההקשר.

--------------------------------------------------
זמן
--------------------------------------------------

בוקר:
06:00–12:00

צהריים:
12:00–17:00

ערב:
17:00–23:59

לילה:
21:00–23:59

גם אם המשתמש כתב וריאציה,
שגיאת כתיב או ניסוח טבעי,
יש להחזיר את הטווח המתאים
כאשר המשמעות ברורה.

--------------------------------------------------
קהל יעד
--------------------------------------------------

לנשים
->
נשים

לגברים
->
גם לגברים

גם לגברים
->
גם לגברים

לגברים ולנשים
->
גם לגברים

--------------------------------------------------
כללים נוספים
--------------------------------------------------

אל תמציא:
- מרכז
- מדריך
- סניף
- יום
- שעה
- גיל
- מיקום
- קהל יעד

שאינם מופיעים
או ניתנים להבנה בבירור.

אל תחזיר את היום הנוכחי
אם המשתמש לא כתב:
היום
מחר
אתמול
שם של יום
או וריאציה ברורה שלו.

--------------------------------------------------
דוגמאות
--------------------------------------------------

"מה יש היום?"
->
intent="activity"
day={current_day}

"מה יש בערב?"
->
intent="activity"
day=None

"אני רוצה משהו בערב"
->
intent="unknown"
interpretation_confident=False
day=None

"מה יש ברבעי?"
->
intent="activity"
day="רביעי"

"חוגים במרקז הדס"
->
intent="activity"
center_name="הדס"

"מה יש בבקר?"
->
intent="activity"
start_after="06:00"
start_before="12:00"

אל תענה למשתמש.
החזר רק את המבנה.
"""

    result = fallback_parser.invoke(
        [
            (
                "system",
                system_instruction,
            ),
            (
                "human",
                user_message,
            ),
        ]
    )

    return _postprocess_parsed_request(
        user_message,
        result,
    )


# ---------------------------------------------------------
# Terminal support
# ---------------------------------------------------------

def _ensure_utf8_stdout() -> None:
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


# ---------------------------------------------------------
# Manual tests
# ---------------------------------------------------------

if __name__ == "__main__":
    _ensure_utf8_stdout()

    print(
        "היום לפי המערכת:",
        _hebrew_day_for_date(
            datetime.now()
        ),
    )

    questions = [
        # Direct short searches
        "מה יש היום?",
        "מה יש מחר?",
        "מה יש בערב?",
        "יש משהו היום?",
        "יש משו מחר?",

        # Semantic time understanding
        "מה יש בבקר?",
        "מה יש בקר?",
        "מה יש על הבוקר?",

        # Vague requests -> clarification
        "אני רוצה משהו בערב",
        "אני רוצה משהו ביום רביעי",
        "אני מחפש משהו בבוקר",
        "אני מחפשת משהו מחר בערב",
        "בא לי משהו בערב",

        # Important typo + context test
        "אני רוצה משהו ביום רבעי בבקר לגברים",

        # Audience normalization
        "אילו חוגים יש לגברים ביום שני?",
        "אילו חוגים יש לנשים ביום ראשון?",

        # Age
        "אילו חוגים מתאימים לגיל 16?",
        "אני בן 14, מה יש ביום שלישי?",
        "אני בת 12 ומחפשת חוג ביום רביעי",

        # Clear category
        "פילאטיס",
        "יוגה",

        # Day hallucination
        "אילו חוגים יש בערב?",
        "אילו חוגים יש בלילה?",
        "אילו חוגים יש היום?",
        "אילו חוגים יש מחר?",
        "אילו חוגים יש ביום שלישי?",
        "אילו חוגים יש ביום שלשי?",

        # Fields
        "אילו חוגים יש במרכז הדס?",
        "אילו חוגים יש במרכז מעיין?",
        "אילו חוגים משה מעביר?",
        "אילו חוגים יש במרקז הדס?",

        # Exact / relative time
        "אילו חוגים יש ביום שבת בשעה 03:00?",
        "אילו חוגים יש היום בשעה 18:30?",
        "אילו חוגים יש ביום שלישי אחרי 18:00?",
        "אילו חוגים יש לפני 10:00?",

        # Spelling
        "אילו חוגים יש ביום רבעי בערב?",
        "איזה חוגים יש בשלשי ארב?",
        "מה יש ברבעי ארב?",
    ]

    for question in questions:

        result = parse_user_request(
            question
        )

        print(
            "\n"
            + "—" * 60
        )

        print(
            "שאלה:",
            question,
        )

        print(
            result.model_dump()
        )

        if (
            result.intent == "unknown"
            or not result.interpretation_confident
        ):
            fallback = (
                reinterpret_unclear_request(
                    question
                )
            )

            print(
                "Fallback:"
            )

            print(
                fallback.model_dump()
            )
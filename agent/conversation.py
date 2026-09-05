from __future__ import annotations

import os
from typing import Any, Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from request_parser import (
    parse_user_request,
    reinterpret_unclear_request,
)


load_dotenv()


# מבנה החלטת השיחה

ClearField = Literal[
    "category",
    "age",
    "target_audience",
    "day",
    "time",
    "location",
    "center_name",
    "branch",
    "instructor",
]


class ConversationDecision(BaseModel):

    action: Literal[
        "more",
        "stop",
        "follow_up",
        "use_known_filters",
        "new_query",
        "greeting",
        "thanks",
        "unclear",
    ] = Field(
        description=(
            "הפעולה המתאימה להודעת המשתמש"
        )
    )

    query_fragment: str | None = Field(
        default=None,
        description=(
            "המידע החדש או המשתנה "
            "שהמשתמש הוסיף"
        ),
    )

    clear_fields: list[ClearField] = Field(
        default_factory=list,
        description=(
            "תנאי חיפוש שהמשתמש ביקש להסיר"
        ),
    )


# שדות החיפוש

SEARCH_FIELDS = [
    "category",
    "age",
    "target_audience",
    "day",
    "start_after",
    "start_before",
    "location",
    "center_name",
    "branch",
    "instructor",
]


# מודל השיחה

def _get_conversation_model():

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        raise RuntimeError(
            "OPENAI_API_KEY לא נמצא "
            "יש לבדוק את קובץ הסביבה"
        )

    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    return model.with_structured_output(
        ConversationDecision
    )


conversation_model = (
    _get_conversation_model()
)


# עיבוד טקסט

def normalize_text(
    text: str,
) -> str:

    return " ".join(
        text
        .strip()
        .casefold()
        .split()
    )


def strip_common_punctuation(
    text: str,
) -> str:

    return text.strip(
        "?!.,:;׳״\"'…"
    )


def is_symbol_only_message(
    text: str,
) -> bool:

    stripped = (
        text.strip()
    )

    if not stripped:
        return True

    return not any(
        character.isalnum()
        for character in stripped
    )


def neutralize_response_text(
    text: str,
) -> str:

    replacements = {
        "הבנתי שאת מחפשת":
            "הבנתי שמחפשים",

        "הבנתי שאתה מחפש":
            "הבנתי שמחפשים",

        "לא הצלחתי להבין בדיוק איזה חוג את מחפשת":
            "לא הצלחתי להבין בדיוק איזה חוג מחפשים",

        "לא הצלחתי להבין בדיוק איזה חוג אתה מחפש":
            "לא הצלחתי להבין בדיוק איזה חוג מחפשים",

        "את מחפשת":
            "מחפשים",

        "אתה מחפש":
            "מחפשים",
    }

    result = text

    for old_text, new_text in replacements.items():

        result = result.replace(
            old_text,
            new_text,
        )

    return result


# כללים מהירים

def is_greeting(
    text: str,
) -> bool:

    normalized = (
        strip_common_punctuation(
            normalize_text(
                text
            )
        )
    )

    greetings = {
        "שלום",
        "היי",
        "הי",
        "הלו",
        "אהלן",
        "בוקר טוב",
        "צהריים טובים",
        "ערב טוב",
        "לילה טוב",
        "מה נשמע",
        "מה קורה",
    }

    return (
        normalized
        in greetings
    )


def is_thanks(
    text: str,
) -> bool:

    normalized = (
        strip_common_punctuation(
            normalize_text(
                text
            )
        )
    )

    thanks_messages = {
        "תודה",
        "תודה רבה",
        "המון תודה",
        "תודה לך",
        "תודה רבה לך",
        "מעולה תודה",
        "אחלה תודה",
        "סבבה תודה",
    }

    return (
        normalized
        in thanks_messages
    )


def looks_like_thanks_or_stop(
    text: str,
) -> bool:

    normalized = (
        normalize_text(
            text
        )
    )

    stop_signals = [
        "מספיק",
        "לא צריך",
        "זה מספיק",
        "סיימתי",
        "עזוב",
        "עזבי",
    ]

    thanks_signals = [
        "תודה",
        "תודע",
        "תודהה",
    ]

    return (
        any(
            signal in normalized
            for signal in stop_signals
        )
        or any(
            signal in normalized
            for signal in thanks_signals
        )
    )


def is_more_request(
    text: str,
) -> bool:

    normalized = (
        strip_common_punctuation(
            normalize_text(
                text
            )
        )
    )

    positive_answers = {
        "כן",
        "כן בבקשה",
        "כן בבקש",
        "בטח",
        "בטח שכן",
        "יאללה",
        "יאללה עוד",
        "בסדר",
        "אוקיי",
        "אוקי",
        "אפשר",
        "אפשר עוד",
        "אפשר בבקשה",
        "אפשר להמשיך",
        "אפשר המשיך",
        "עוד",
        "תמשיך",
        "תמשיכי",
    }

    if normalized in positive_answers:
        return True

    if (
        "עוד" in normalized
        and not normalized.startswith(
            "לא"
        )
    ):
        return True

    return False


def is_stop_more_request(
    text: str,
) -> bool:

    normalized = (
        strip_common_punctuation(
            normalize_text(
                text
            )
        )
    )

    if "מספיק" in normalized:
        return True

    if normalized.startswith(
        "לא"
    ):
        return True

    if "לא צריך" in normalized:
        return True

    if looks_like_thanks_or_stop(
        normalized
    ):
        return True

    return False


# בדיקת תנאי חיפוש

def has_meaningful_search_filters(
    state: dict[str, Any],
) -> bool:

    return any(
        state.get(
            field
        ) is not None
        for field in SEARCH_FIELDS
    )


def state_to_context_text(
    state: dict[str, Any],
) -> str:

    parts: list[str] = []

    category = state.get(
        "category"
    )

    if category:
        parts.append(
            f"סוג חוג: {category}"
        )

    day = state.get(
        "day"
    )

    if day:
        parts.append(
            f"יום: {day}"
        )

    start_after = state.get(
        "start_after"
    )

    start_before = state.get(
        "start_before"
    )

    if (
        start_after
        and start_before
        and start_after == start_before
    ):
        parts.append(
            f"שעה מדויקת: {start_after}"
        )

    elif (
        start_after == "17:00"
        and start_before == "23:59"
    ):
        parts.append(
            "זמן: ערב"
        )

    elif (
        start_after == "21:00"
        and start_before == "23:59"
    ):
        parts.append(
            "זמן: לילה"
        )

    elif (
        start_after == "06:00"
        and start_before == "12:00"
    ):
        parts.append(
            "זמן: בוקר"
        )

    elif (
        start_after == "12:00"
        and start_before == "17:00"
    ):
        parts.append(
            "זמן: צהריים"
        )

    else:

        if start_after:
            parts.append(
                f"אחרי: {start_after}"
            )

        if start_before:
            parts.append(
                f"לפני: {start_before}"
            )

    center_name = state.get(
        "center_name"
    )

    if center_name:
        parts.append(
            f"מרכז: {center_name}"
        )

    branch = state.get(
        "branch"
    )

    if branch:
        parts.append(
            f"סניף: {branch}"
        )

    instructor = state.get(
        "instructor"
    )

    if instructor:
        parts.append(
            f"מדריך: {instructor}"
        )

    location = state.get(
        "location"
    )

    if location:
        parts.append(
            f"מיקום: {location}"
        )

    target_audience = state.get(
        "target_audience"
    )

    if target_audience:
        parts.append(
            f"קהל: {target_audience}"
        )

    age = state.get(
        "age"
    )

    if age is not None:
        parts.append(
            f"גיל: {age}"
        )

    if not parts:
        return (
            "אין פילטרים קודמים"
        )

    return "\n".join(
        parts
    )


def build_query_from_state(
    state: dict[str, Any],
) -> str:

    parts: list[str] = []

    category = state.get(
        "category"
    )

    if category:
        parts.append(
            str(
                category
            )
        )

    else:
        parts.append(
            "חוגים"
        )

    day = state.get(
        "day"
    )

    if day:
        parts.append(
            f"ביום {day}"
        )

    start_after = state.get(
        "start_after"
    )

    start_before = state.get(
        "start_before"
    )

    if (
        start_after == "17:00"
        and start_before == "23:59"
    ):
        parts.append(
            "בערב"
        )

    elif (
        start_after == "21:00"
        and start_before == "23:59"
    ):
        parts.append(
            "בלילה"
        )

    elif (
        start_after == "06:00"
        and start_before == "12:00"
    ):
        parts.append(
            "בבוקר"
        )

    elif (
        start_after == "12:00"
        and start_before == "17:00"
    ):
        parts.append(
            "בצהריים"
        )

    elif (
        start_after
        and start_before
        and start_after == start_before
    ):
        parts.append(
            f"בשעה {start_after}"
        )

    elif start_after:
        parts.append(
            f"אחרי {start_after}"
        )

    elif start_before:
        parts.append(
            f"לפני {start_before}"
        )

    center_name = state.get(
        "center_name"
    )

    if center_name:
        parts.append(
            f"במרכז {center_name}"
        )

    branch = state.get(
        "branch"
    )

    if branch:
        parts.append(
            f"בסניף {branch}"
        )

    location = state.get(
        "location"
    )

    if location:
        parts.append(
            f"במיקום {location}"
        )

    instructor = state.get(
        "instructor"
    )

    if instructor:
        parts.append(
            f"עם המדריך {instructor}"
        )

    target_audience = state.get(
        "target_audience"
    )

    if target_audience:
        parts.append(
            f"לקהל {target_audience}"
        )

    age = state.get(
        "age"
    )

    if age is not None:
        parts.append(
            f"לגיל {age}"
        )

    return (
        "אילו "
        + " ".join(
            parts
        )
        + "?"
    )


# נרמול המשך שיחה

def normalize_follow_up_fragment(
    query_fragment: str,
) -> str:

    fragment = (
        query_fragment
        .strip()
    )

    if not fragment:
        return fragment

    normalized = (
        normalize_text(
            fragment
        )
    )

    complete_query_signals = [
        "חוג",
        "חוגים",
        "שיעור",
        "שיעורים",
        "מה יש",
        "אילו",
        "איזה",
        "יש משהו",
        "יש משו",
    ]

    if any(
        signal in normalized
        for signal in complete_query_signals
    ):
        return fragment

    return (
        f"אילו חוגים יש "
        f"{fragment}?"
    )


# הסרת תנאים

def apply_clear_fields(
    state: dict[str, Any],
    clear_fields: list[ClearField],
) -> None:

    for field in clear_fields:

        if field == "time":

            state[
                "start_after"
            ] = None

            state[
                "start_before"
            ] = None

        elif field in SEARCH_FIELDS:

            state[
                field
            ] = None


def detect_clear_fields_from_text(
    user_message: str,
) -> list[ClearField]:

    text = (
        normalize_text(
            user_message
        )
    )

    clear_fields: list[
        ClearField
    ] = []

    center_signals = [
        "בלי מרכז",
        "לא משנה המרכז",
        "לא משנה איזה מרכז",
        "עזוב את המרכז",
        "עזבי את המרכז",
        "כל מרכז",
    ]

    if any(
        signal in text
        for signal in center_signals
    ):
        clear_fields.append(
            "center_name"
        )

    day_signals = [
        "בלי יום",
        "לא משנה היום",
        "כל יום",
        "בלי יום מסוים",
    ]

    if any(
        signal in text
        for signal in day_signals
    ):
        clear_fields.append(
            "day"
        )

    time_signals = [
        "בכל שעה",
        "בלי שעה",
        "לא משנה השעה",
        "כל שעה",
        "לא משנה הזמן",
    ]

    if any(
        signal in text
        for signal in time_signals
    ):
        clear_fields.append(
            "time"
        )

    instructor_signals = [
        "בלי מדריך",
        "לא משנה המדריך",
        "כל מדריך",
    ]

    if any(
        signal in text
        for signal in instructor_signals
    ):
        clear_fields.append(
            "instructor"
        )

    age_signals = [
        "בלי גיל",
        "לא משנה הגיל",
        "כל גיל",
    ]

    if any(
        signal in text
        for signal in age_signals
    ):
        clear_fields.append(
            "age"
        )

    category_signals = [
        "בלי סוג",
        "לא משנה הסוג",
        "כל חוג",
        "כל פעילות",
    ]

    if any(
        signal in text
        for signal in category_signals
    ):
        clear_fields.append(
            "category"
        )

    return list(
        dict.fromkeys(
            clear_fields
        )
    )


# סיווג הודעת השיחה

def classify_conversation_message(
    user_message: str,
    previous_state: dict[str, Any] | None,
    waiting_for_more: bool,
    waiting_for_clarification: bool,
) -> ConversationDecision:

    previous_state = (
        previous_state
        or {}
    )

    previous_context = (
        state_to_context_text(
            previous_state
        )
    )

    if waiting_for_more:

        mode = (
            "הסוכן שאל אם יש רצון "
            "לראות תוצאות נוספות"
        )

    elif waiting_for_clarification:

        mode = (
            "הסוכן ביקש הבהרה "
            "לגבי חיפוש קודם"
        )

    elif previous_state:

        mode = (
            "יש חיפוש קודם פעיל "
            "וההודעה יכולה להיות המשך"
        )

    else:

        mode = (
            "אין הקשר חיפוש פעיל"
        )

    system_instruction = f"""
אתה רכיב להבנת מהלך שיחה
במערכת לחיפוש חוגים

אל תחפש בדאטה ואל תענה למשתמש

מצב השיחה
{mode}

הפילטרים הקודמים
{previous_context}

בחר action

more
בקשה לראות עוד תוצאות

stop
בקשה לעצור או לסיים

follow_up
שינוי הוספה הסרה או חזרה על תנאי
מהחיפוש הקודם

כאשר קיימים פילטרים קודמים
והמשתמש ממשיך את השיחה בניסוח כמו
ומה
ואיזה
ואילו
ומה עם
ומה לגבי
יש להתייחס להודעה כהמשך לחיפוש הקודם
גם אם המשתמש חוזר על תנאי שכבר קיים

use_known_filters
רק כאשר הסוכן מחכה להבהרה
והמשתמש אומר שאין העדפה נוספת
ורוצה להמשיך עם המידע שכבר ידוע

במקרה כזה
query_fragment=None
clear_fields=[]

new_query
חיפוש חדש ועצמאי שאינו תלוי בחיפוש הקודם

אין לבחור new_query
כאשר ההודעה מנוסחת כהמשך ברור לשיחה הקודמת
גם אם התנאי שהמשתמש ציין זהה לתנאי שכבר קיים

greeting
ברכה

thanks
תודה

unclear
רק אם באמת אי אפשר להבין

כאשר action="follow_up"
ב query_fragment יש להחזיר
רק את המידע החדש או המשתנה

דוגמאות

מצב קודם
פילאטיס בערב

הודעה
ומה ביום רביעי

action="follow_up"
query_fragment="ביום רביעי"
clear_fields=[]

מצב קודם
חוגים ביום שלישי בערב

הודעה
ומה בערב

action="follow_up"
query_fragment="בערב"
clear_fields=[]

מצב קודם
חוגים ביום שלישי בבוקר

הודעה
ומה בבוקר

action="follow_up"
query_fragment="בבוקר"
clear_fields=[]

מצב קודם
פילאטיס ביום רביעי בערב

הודעה
ומה בבוקר

action="follow_up"
query_fragment="בבוקר"
clear_fields=[]

מצב קודם
פילאטיס ביום שלישי בערב

הודעה
ומה במרכז מעיין

action="follow_up"
query_fragment="במרכז מעיין"
clear_fields=[]

מצב קודם
פילאטיס ביום רביעי בבוקר במרכז הדס

הודעה
ומה ברבעי ארב

action="follow_up"
query_fragment="ביום רביעי בערב"
clear_fields=[]

מצב קודם
חוגים ביום שלישי בערב

הודעה
פילאטיס ביום שלישי בערב

action="new_query"
query_fragment=None
clear_fields=[]

כאשר המשתמש כותב בקשת חיפוש מלאה ועצמאית
שכוללת סוג חוג יחד עם יום שעה מרכז מדריך או תנאי נוסף
יש לבחור new_query
גם אם ההודעה קצרה

כאשר המשתמש מבקש לבטל תנאי קודם
יש להחזיר אותו ב clear_fields

אפשרויות
category
age
target_audience
day
time
location
center_name
branch
instructor

דוגמאות

ומה בלי מרכז מסוים

action="follow_up"
query_fragment=None
clear_fields=["center_name"]

בכל שעה

action="follow_up"
query_fragment=None
clear_fields=["time"]

בלי יום מסוים

action="follow_up"
query_fragment=None
clear_fields=["day"]

לא משנה המרכז ביום חמישי

action="follow_up"
query_fragment="ביום חמישי"
clear_fields=["center_name"]

יש להבין שגיאות כתיב סבירות

שלשי הוא שלישי
רבעי הוא רביעי
ארב הוא ערב
מרקז הוא מרכז
תודע היא תודה
בבקש הוא בבקשה

אם מחכים לעוד תוצאות

כן
כן בבקשה
כן בבקש
אפשר להמשיך
אפשר המשיך
תראה עוד
יאללה עוד

action="more"

מספיק
לא צריך
מספיק תודע
תודה זה מספיק

action="stop"

אם התבקשה הבהרה
והתגובה היא למשל

פילאטיס
יוגה
במרכז הדס
משה
בבוקר
ביום שלישי

זו בדרך כלל תשובת follow_up

אם התבקשה הבהרה
והמשתמש מביע שאין לו העדפה נוספת
למשל

לא משנה
אין העדפה
מה שיש
לא חשוב
לא אכפת לי
אפשר מה שיש

יש לבחור

action="use_known_filters"
query_fragment=None
clear_fields=[]

חשוב

אל תמציא פילטרים

אל תחזיר מידע ישן בתוך query_fragment

clear_fields מיועד רק לתנאים שהמשתמש ביקש להסיר

ניתן להחזיר גם query_fragment וגם clear_fields יחד

אל תענה למשתמש
"""

    try:

        decision = (
            conversation_model.invoke(
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
        )

        deterministic_clear_fields = (
            detect_clear_fields_from_text(
                user_message
            )
        )

        decision.clear_fields = list(
            dict.fromkeys(
                [
                    *decision.clear_fields,
                    *deterministic_clear_fields,
                ]
            )
        )

        if (
            waiting_for_clarification
            and decision.action
            == "follow_up"
            and decision.query_fragment
            is None
            and not decision.clear_fields
        ):
            decision.action = (
                "use_known_filters"
            )

        return decision

    except Exception as error:

        print(
            "Conversation classification error:",
            repr(
                error
            ),
        )

        return ConversationDecision(
            action="unclear",
            query_fragment=None,
            clear_fields=(
                detect_clear_fields_from_text(
                    user_message
                )
            ),
        )


def _parse_follow_up_fragment(
    query_fragment: str,
) -> dict[str, Any]:

    normalized_fragment = (
        normalize_follow_up_fragment(
            query_fragment
        )
    )

    parsed = (
        parse_user_request(
            normalized_fragment
        )
    )

    if not (
        parsed.interpretation_confident
    ):

        parsed = (
            reinterpret_unclear_request(
                normalized_fragment
            )
        )

    return {
        "category":
            parsed.category,
        "age":
            parsed.age,
        "target_audience":
            parsed.target_audience,
        "day":
            parsed.day,
        "start_after":
            parsed.start_after,
        "start_before":
            parsed.start_before,
        "location":
            parsed.location,
        "center_name":
            parsed.center_name,
        "branch":
            parsed.branch,
        "instructor":
            parsed.instructor,
    }


def merge_follow_up(
    previous_state: dict[str, Any],
    query_fragment: str | None,
    clear_fields: list[ClearField] | None = None,
) -> str:

    merged_state = {
        field:
            previous_state.get(
                field
            )
        for field in SEARCH_FIELDS
    }

    apply_clear_fields(
        merged_state,
        clear_fields or [],
    )

    if not query_fragment:

        return (
            build_query_from_state(
                merged_state
            )
        )

    fragment_state = (
        _parse_follow_up_fragment(
            query_fragment
        )
    )

    for field in SEARCH_FIELDS:

        if field in {
            "start_after",
            "start_before",
        }:
            continue

        new_value = (
            fragment_state.get(
                field
            )
        )

        if new_value is not None:

            merged_state[
                field
            ] = new_value

    fragment_start_after = (
        fragment_state.get(
            "start_after"
        )
    )

    fragment_start_before = (
        fragment_state.get(
            "start_before"
        )
    )

    if (
        fragment_start_after
        is not None
        or fragment_start_before
        is not None
    ):

        merged_state[
            "start_after"
        ] = (
            fragment_start_after
        )

        merged_state[
            "start_before"
        ] = (
            fragment_start_before
        )

    return (
        build_query_from_state(
            merged_state
        )
    )


# בדיקת קשר לשיחה קודמת

def should_check_conversation_context(
    user_message: str,
    previous_state: dict[str, Any],
) -> bool:

    if not previous_state:
        return False

    normalized = (
        normalize_text(
            user_message
        )
    )

    words = (
        normalized.split()
    )

    standalone_query_starts = [
        "מה יש",
        "אילו ",
        "איזה ",
        "איפה יש",
        "באילו ימים",
        "יש משהו",
        "יש משו",
        "אני רוצה",
        "אני מחפש",
        "אני מחפשת",
        "בא לי",
    ]

    if any(
        normalized.startswith(
            signal
        )
        for signal in standalone_query_starts
    ):
        return False

    follow_up_signals = [
        "ומה",
        "ואיזה",
        "ואילו",
        "וביום",
        "ובערב",
        "ובבוקר",
        "ובלילה",
        "ואיפה",
        "ומה עם",
        "ומה לגבי",
        "יש גם",
        "גם ביום",
        "גם בערב",
        "בלי",
        "לא משנה",
        "עזוב את",
        "עזבי את",
        "בכל שעה",
        "כל שעה",
        "כל יום",
    ]

    if any(
        signal in normalized
        for signal in follow_up_signals
    ):
        return True

    fragment_starts = [
        "ביום ",
        "בבוקר",
        "בערב",
        "בצהריים",
        "בלילה",
        "במרכז ",
        "מרכז ",
        "בסניף ",
        "במיקום ",
        "עם המדריך ",
        "עם מדריך ",
        "מדריך ",
        "לגיל ",
        "לקהל ",
    ]

    if any(
        normalized.startswith(
            signal
        )
        for signal in fragment_starts
    ):
        return True

    weekdays = {
        "ראשון",
        "שני",
        "שלישי",
        "רביעי",
        "חמישי",
        "שישי",
        "שבת",
    }

    if (
        words
        and words[0] in weekdays
    ):
        return True

    if len(
        words
    ) == 1:
        return True

    return False
from __future__ import annotations

import asyncio
import os
from typing import Any, Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from graph import graph
from tools import format_activity_hebrew


load_dotenv()

PAGE_SIZE = 5


# ---------------------------------------------------------
# Telegram UI
# ---------------------------------------------------------

CB_SEARCH = "search"
CB_TODAY = "today"
CB_TOMORROW = "tomorrow"
CB_MORNING = "morning"
CB_EVENING = "evening"
CB_MORE = "more"
CB_NO_PREFERENCE = "no_preference"
CB_NEW_SEARCH = "new_search"
CB_HELP = "help"


START_TEXT = (
    "שלום! 👋\n\n"
    "אני Community Center AI Agent 🤖 — "
    "סוכן AI חכם לחיפוש חוגים ופעילויות "
    "במרכזי הספורט הקהילתיים.\n\n"

    "אפשר לדבר איתי בעברית חופשית, "
    "ואני יודע להבין גם המשכים לשיחה "
    "ושגיאות כתיב סבירות.\n\n"

    "אפשר לחפש לפי:\n"
    "• יום — כולל היום ומחר\n"
    "• שעה או חלק ביום — בוקר / צהריים / ערב / לילה\n"
    "• סוג חוג\n"
    "• מרכז וסניף\n"
    "• מדריך/ה\n"
    "• מיקום\n"
    "• קהל יעד\n"
    "• גיל, כאשר קיים מידע גיל במקור\n\n"

    "דוגמאות:\n"
    "• מה יש מחר בערב?\n"
    "• אילו חוגי פילאטיס יש ביום שלישי?\n"
    "• מה יש במרכז הדס?\n"
    "• אילו חוגים משה מעביר?\n"
    "• אילו חוגים מתאימים לגיל 16?\n\n"

    "אפשר לכתוב שאלה חופשית "
    "או לבחור פעולה מהכפתורים 👇"
)


HELP_TEXT = (
    "🤖 איך משתמשים ב-Community Center AI Agent?\n\n"

    "אפשר פשוט לכתוב שאלה טבעית, למשל:\n"
    "• מה יש היום?\n"
    "• מה יש מחר בערב?\n"
    "• אילו חוגי פילאטיס יש ביום שלישי?\n"
    "• מה יש במרכז הדס?\n"
    "• אילו חוגים משה מעביר?\n"
    "• אילו חוגים מתאימים לגיל 16?\n\n"

    "אפשר גם להמשיך חיפוש קיים בשיחה טבעית:\n"
    "• ומה בבוקר?\n"
    "• ומה במרכז מעיין?\n"
    "• ומה ביום רביעי?\n"
    "• ומה בלי קהל מסוים?\n"
    "• לא משנה / אין לי העדפה\n\n"

    "אם קיימות תוצאות נוספות, "
    "אפשר להשתמש בכפתור \"📄 הצג עוד\".\n\n"

    "/reset — איפוס השיחה והתחלת חיפוש חדש"
)

"""
בונה את תפריט הכפתורים הראשי של הבוט
ומחזירה את אפשרויות החיפוש המרכזיות למשתמש
"""
def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔎 חיפוש חוגים",
                    callback_data=CB_SEARCH,
                )
            ],
            [
                InlineKeyboardButton(
                    "📅 היום",
                    callback_data=CB_TODAY,
                ),
                InlineKeyboardButton(
                    "➡️ מחר",
                    callback_data=CB_TOMORROW,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌅 בוקר",
                    callback_data=CB_MORNING,
                ),
                InlineKeyboardButton(
                    "🌆 ערב",
                    callback_data=CB_EVENING,
                ),
            ],
            [
                InlineKeyboardButton(
                    "❓ עזרה",
                    callback_data=CB_HELP,
                ),
                InlineKeyboardButton(
                    "🔄 חיפוש חדש",
                    callback_data=CB_NEW_SEARCH,
                ),
            ],
        ]
    )

"""
בונה את תפריט הכפתורים לאחר הצגת תוצאות החיפוש
ומוסיפה אפשרות להצגת תוצאות נוספות כאשר קיימות תוצאות נוספות
"""
def _results_keyboard(
    has_more: bool,
) -> InlineKeyboardMarkup:

    rows: list[
        list[InlineKeyboardButton]
    ] = []

    if has_more:
        rows.append(
            [
                InlineKeyboardButton(
                    "📄 הצג עוד",
                    callback_data=CB_MORE,
                ),
                InlineKeyboardButton(
                    "🔄 חיפוש חדש",
                    callback_data=CB_NEW_SEARCH,
                ),
            ]
        )

    else:
        rows.append(
            [
                InlineKeyboardButton(
                    "🔄 חיפוש חדש",
                    callback_data=CB_NEW_SEARCH,
                )
            ]
        )

    rows.extend(
        [
            [
                InlineKeyboardButton(
                    "🌅 בוקר",
                    callback_data=CB_MORNING,
                ),
                InlineKeyboardButton(
                    "🌆 ערב",
                    callback_data=CB_EVENING,
                ),
            ],
            [
                InlineKeyboardButton(
                    "📅 היום",
                    callback_data=CB_TODAY,
                ),
                InlineKeyboardButton(
                    "➡️ מחר",
                    callback_data=CB_TOMORROW,
                ),
            ],
            [
                InlineKeyboardButton(
                    "❓ עזרה",
                    callback_data=CB_HELP,
                )
            ],
        ]
    )

    return InlineKeyboardMarkup(
        rows
    )

"""
בונה תפריט כפתורים כאשר נדרש מידע נוסף מהמשתמש
ומאפשרת להשלים את החיפוש או להמשיך ללא העדפה נוספת
"""
def _clarification_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ אין לי העדפה",
                    callback_data=CB_NO_PREFERENCE,
                )
            ],
            [
                InlineKeyboardButton(
                    "🌅 בוקר",
                    callback_data=CB_MORNING,
                ),
                InlineKeyboardButton(
                    "🌆 ערב",
                    callback_data=CB_EVENING,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 חיפוש חדש",
                    callback_data=CB_NEW_SEARCH,
                ),
                InlineKeyboardButton(
                    "❓ עזרה",
                    callback_data=CB_HELP,
                ),
            ],
        ]
    )


# ---------------------------------------------------------
# Conversation understanding
# ---------------------------------------------------------

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

"""
מגדירה את מבנה ההחלטה של שכבת השיחה
ושומרת את סוג הפעולה המידע החדש והפילטרים שיש להסיר
"""
class ConversationDecision(BaseModel):
    """
    החלטה לגבי משמעות הודעת המשתמש
    בתוך הקשר השיחה.
    """

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
            "כאשר מדובר ב-follow_up, "
            "רק המידע החדש או המשתנה "
            "שהמשתמש הוסיף"
        ),
    )

    clear_fields: list[ClearField] = Field(
        default_factory=list,
        description=(
            "פילטרים קודמים שהמשתמש ביקש "
            "להסיר מהחיפוש"
        ),
    )


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------
"""
קוראת את מפתח הטלגרם ממשתני הסביבה
ומוודאת שהמפתח קיים לפני הפעלת הבוט
"""
def _get_bot_token() -> str:

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN לא נמצא. "
            "יש לבדוק את קובץ .env."
        )

    return token

"""
יוצרת את מודל השיחה
ומגדירה שהפלט יחזור במבנה קבוע ומסודר
"""
def _get_conversation_model():

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        raise RuntimeError(
            "OPENAI_API_KEY לא נמצא. "
            "יש לבדוק את קובץ .env."
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


# ---------------------------------------------------------
# Text helpers
# ---------------------------------------------------------
"""
מנרמלת את הטקסט לצורך השוואה עקבית
ומסירה רווחים מיותרים
"""
def _normalize_text(
    text: str,
) -> str:

    return " ".join(
        text
        .strip()
        .casefold()
        .split()
    )

"""
מסירה סימני פיסוק נפוצים מתחילת הטקסט ומסופו
כדי לשפר את ההשוואה בין הודעות
"""
def _strip_common_punctuation(
    text: str,
) -> str:

    return text.strip(
        "?!.,:;׳״\"'…"
    )

"""
בודקת האם ההודעה מכילה רק סימנים
כדי להתעלם מהודעות ללא תוכן שימושי
"""
def _is_symbol_only_message(
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

"""
ממירה ניסוחים תלויי מגדר לניסוחים ניטרליים
כדי להתאים את התשובה לכל משתמש
"""
def _neutralize_response_text(
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


# ---------------------------------------------------------
# Fast deterministic rules
# ---------------------------------------------------------
"""
בודקת האם הודעת המשתמש היא ברכה מוכרת
כדי לאפשר תגובה ישירה ללא שימוש במודל השפה
"""
def _is_greeting(
    text: str,
) -> bool:

    normalized = (
        _strip_common_punctuation(
            _normalize_text(
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

"""
בודקת האם הודעת המשתמש היא הודעת תודה מוכרת
כדי לאפשר תגובה ישירה ללא שימוש במודל השפה
"""
def _is_thanks(
    text: str,
) -> bool:

    normalized = (
        _strip_common_punctuation(
            _normalize_text(
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

"""
בודקת האם ההודעה מביעה תודה או רצון לסיים
כדי לזהות במהירות הודעות שאינן דורשות חיפוש נוסף
"""
def _looks_like_thanks_or_stop(
    text: str,
) -> bool:

    normalized = (
        _normalize_text(
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

"""
בודקת האם המשתמש מבקש לראות תוצאות נוספות
לפי ניסוחים נפוצים של אישור או בקשה להמשך
"""
def _is_more_request(
    text: str,
) -> bool:

    normalized = (
        _strip_common_punctuation(
            _normalize_text(
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

"""
בודקת האם המשתמש רוצה לעצור את הצגת התוצאות הנוספות
ולסיים את שלב ההמשך של החיפוש
"""
def _is_stop_more_request(
    text: str,
) -> bool:

    normalized = (
        _strip_common_punctuation(
            _normalize_text(
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

    if _looks_like_thanks_or_stop(
        normalized
    ):
        return True

    return False


# ---------------------------------------------------------
# Search-context helpers
# ---------------------------------------------------------

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

"""
בודקת האם במצב החיפוש קיים לפחות תנאי חיפוש אחד
שאפשר להשתמש בו לביצוע החיפוש
"""
def _has_meaningful_search_filters(
    state: dict[str, Any],
) -> bool:

    return any(
        state.get(
            field
        ) is not None
        for field in SEARCH_FIELDS
    )

"""
ממירה את מצב החיפוש הקודם לטקסט ברור
כדי להעביר לשכבת השיחה את המידע שכבר ידוע
"""
def _state_to_context_text(
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
            "אין פילטרים קודמים."
        )

    return "\n".join(
        parts
    )

"""
בונה שאלת חיפוש מלאה מתוך המידע השמור במצב השיחה
כדי לשלוח בקשה ברורה לתהליך החיפוש
"""
def _build_query_from_state(
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


# ---------------------------------------------------------
# Fragment normalization
# ---------------------------------------------------------
"""
מנרמלת מידע חדש שהתקבל בשאלת המשך
והופכת אותו לשאלת חיפוש מלאה כאשר נדרש
"""
def _normalize_follow_up_fragment(
    query_fragment: str,
) -> str:

    fragment = (
        query_fragment
        .strip()
    )

    if not fragment:
        return fragment

    normalized = (
        _normalize_text(
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


# ---------------------------------------------------------
# Clear-field helpers
# ---------------------------------------------------------
"""
מסירה ממצב החיפוש פילטרים שהמשתמש ביקש לבטל
ומעדכנת את תנאי החיפוש השמורים
"""
def _apply_clear_fields(
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

"""
מזהה מתוך הודעת המשתמש אילו תנאי חיפוש יש להסיר
לפי ניסוחים קבועים ומוכרים מראש
"""
def _detect_clear_fields_from_text(
    user_message: str,
) -> list[ClearField]:

    text = (
        _normalize_text(
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


# ---------------------------------------------------------
# LLM conversation classification
# ---------------------------------------------------------
"""
מנתחת את הודעת המשתמש בהתאם להקשר השיחה הקודם
ומחליטה אם מדובר בחיפוש חדש המשך שיחה עצירה או בקשה נוספת
"""
def _classify_conversation_message(
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
        _state_to_context_text(
            previous_state
        )
    )

    if waiting_for_more:

        mode = (
            "הסוכן שאל אם יש רצון "
            "לראות תוצאות נוספות."
        )

    elif waiting_for_clarification:

        mode = (
            "הסוכן ביקש הבהרה "
            "לגבי חיפוש קודם."
        )

    elif previous_state:

        mode = (
            "יש חיפוש קודם פעיל "
            "וההודעה יכולה להיות המשך."
        )

    else:

        mode = (
            "אין הקשר חיפוש פעיל."
        )

    system_instruction = f"""
אתה רכיב להבנת מהלך שיחה
בבוט לחיפוש חוגים.

אל תחפש בדאטה ואל תענה למשתמש.

מצב השיחה:
{mode}

הפילטרים הקודמים:
{previous_context}

בחר action:

more:
בקשה לראות עוד תוצאות.

stop:
בקשה לעצור או לסיים.

follow_up:
שינוי, הוספה או הסרה של תנאי
מהחיפוש הקודם.

use_known_filters:
רק כאשר הסוכן מחכה להבהרה,
והמשתמש אומר שאין העדפה נוספת
ורוצה להמשיך עם המידע שכבר ידוע.

במקרה כזה:
query_fragment=None
clear_fields=[]

new_query:
חיפוש חדש שאינו תלוי בחיפוש הקודם.

greeting:
ברכה.

thanks:
תודה.

unclear:
רק אם באמת אי אפשר להבין.

כאשר action="follow_up":
ב-query_fragment יש להחזיר
רק את המידע החדש או המשתנה.

דוגמאות:

מצב קודם:
פילאטיס בערב

הודעה:
ומה ביום רביעי?

->
action="follow_up"
query_fragment="ביום רביעי"
clear_fields=[]


מצב קודם:
פילאטיס ביום רביעי בערב

הודעה:
ומה בבוקר?

->
action="follow_up"
query_fragment="בבוקר"
clear_fields=[]


מצב קודם:
פילאטיס ביום שלישי בערב

הודעה:
ומה במרכז מעיין?

->
action="follow_up"
query_fragment="במרכז מעיין"
clear_fields=[]


מצב קודם:
פילאטיס ביום רביעי בבוקר במרכז הדס

הודעה:
ומה ברבעי ארב?

->
action="follow_up"
query_fragment="ביום רביעי בערב"
clear_fields=[]


כאשר המשתמש מבקש לבטל תנאי קודם,
יש להחזיר אותו ב-clear_fields.

אפשרויות:
category
age
target_audience
day
time
location
center_name
branch
instructor


דוגמאות:

ומה בלי מרכז מסוים?

->
action="follow_up"
query_fragment=None
clear_fields=["center_name"]


בכל שעה

->
action="follow_up"
query_fragment=None
clear_fields=["time"]


בלי יום מסוים

->
action="follow_up"
query_fragment=None
clear_fields=["day"]


לא משנה המרכז, ביום חמישי

->
action="follow_up"
query_fragment="ביום חמישי"
clear_fields=["center_name"]


יש להבין שגיאות כתיב סבירות:

שלשי -> שלישי
רבעי -> רביעי
ארב -> ערב
מרקז -> מרכז
תודע -> תודה
בבקש -> בבקשה


אם מחכים לעוד תוצאות:

כן
כן בבקשה
כן בבקש
אפשר להמשיך
אפשר המשיך
תראה עוד
יאללה עוד

->
action="more"


מספיק
לא צריך
מספיק תודע
תודה זה מספיק

->
action="stop"


אם התבקשה הבהרה
והתגובה היא למשל:

פילאטיס
יוגה
במרכז הדס
משה
בבוקר
ביום שלישי

זו בדרך כלל תשובת follow_up.


אם התבקשה הבהרה
והמשתמש מביע שאין לו העדפה נוספת,
בכל ניסוח טבעי או עם שגיאת כתיב,
למשל במשמעות של:

לא משנה
אין העדפה
מה שיש
לא חשוב
לא אכפת לי
אפשר מה שיש

יש לבחור:

action="use_known_filters"
query_fragment=None
clear_fields=[]


חשוב:

1. אל תמציא פילטרים.

2. אל תחזיר מידע ישן
בתוך query_fragment.

3. clear_fields מיועד רק
לפילטרים שהמשתמש ביקש להסיר.

4. ניתן להחזיר גם query_fragment
וגם clear_fields יחד.

5. אל תענה למשתמש.
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
            _detect_clear_fields_from_text(
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
                _detect_clear_fields_from_text(
                    user_message
                )
            ),
        )


# ---------------------------------------------------------
# Follow-up merge
# ---------------------------------------------------------
"""
ממזגת מידע חדש משאלת המשך עם תנאי החיפוש הקודמים
ובונה בקשת חיפוש מלאה ומעודכנת
"""
def _merge_follow_up(
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

    _apply_clear_fields(
        merged_state,
        clear_fields or [],
    )

    if not query_fragment:

        return (
            _build_query_from_state(
                merged_state
            )
        )

    normalized_fragment = (
        _normalize_follow_up_fragment(
            query_fragment
        )
    )

    fragment_result = graph.invoke(
        {
            "user_message":
                normalized_fragment,
        }
    )

    for field in SEARCH_FIELDS:

        if field in {
            "start_after",
            "start_before",
        }:
            continue

        new_value = (
            fragment_result.get(
                field
            )
        )

        if new_value is not None:

            merged_state[
                field
            ] = new_value

    fragment_start_after = (
        fragment_result.get(
            "start_after"
        )
    )

    fragment_start_before = (
        fragment_result.get(
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
        _build_query_from_state(
            merged_state
        )
    )


# ---------------------------------------------------------
# Async wrappers for blocking AI calls
# ---------------------------------------------------------
"""
מריצה את סיווג הודעת השיחה בתהליך נפרד
כדי שעבודת הבוט לא תיעצר בזמן העיבוד
"""
async def _classify_conversation_message_async(
    user_message: str,
    previous_state: dict[str, Any] | None,
    waiting_for_more: bool,
    waiting_for_clarification: bool,
) -> ConversationDecision:
    """
    מריץ את סיווג השיחה ב-thread נפרד,
    כדי לא לחסום את ה-event loop של Telegram.
    """

    return await asyncio.to_thread(
        _classify_conversation_message,
        user_message,
        previous_state,
        waiting_for_more,
        waiting_for_clarification,
    )

"""
מריצה את מיזוג שאלת ההמשך בתהליך נפרד
כדי לשמור על פעילות רציפה של הבוט בזמן העיבוד
"""
async def _merge_follow_up_async(
    previous_state: dict[str, Any],
    query_fragment: str | None,
    clear_fields: list[ClearField] | None = None,
) -> str:
    """
    מריץ את מיזוג ה-follow-up ב-thread נפרד.

    _merge_follow_up עצמו מפעיל את ה-Graph,
    ולכן חשוב שלא יחסום את Telegram
    בזמן שה-Agent עובד.
    """

    return await asyncio.to_thread(
        _merge_follow_up,
        previous_state,
        query_fragment,
        clear_fields,
    )


# ---------------------------------------------------------
# Agent flow
# ---------------------------------------------------------
#
# User message
#      |
#      v
# Telegram conversation layer
#      |
#      v
# Final search message
#      |
#      v
# Graph
#      |
#      v
# Result

"""
מפעילה את תהליך הסוכן בתהליך נפרד
ומעבירה אליו את הודעת המשתמש לצורך עיבוד
"""
async def _invoke_graph_async(
    user_message: str,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        graph.invoke,
        {
            "user_message":
                user_message,
        },
    )


# ---------------------------------------------------------
# Context-check helper
# ---------------------------------------------------------
"""
בודקת האם ההודעה החדשה קשורה לחיפוש הקודם
או שמדובר בבקשת חיפוש חדשה ונפרדת
"""
def _should_check_conversation_context(
    user_message: str,
    previous_state: dict[str, Any],
) -> bool:

    if not previous_state:
        return False

    normalized = (
        _normalize_text(
            user_message
        )
    )

    words = (
        normalized.split()
    )

    # -----------------------------------------------------
    # Complete standalone queries
    # -----------------------------------------------------
    #
    # שאלות מלאות כאלה הן חיפוש חדש,
    # גם אם הן קצרות.
    #
    # לדוגמה:
    # מה יש ביום שלישי?
    # אילו חוגים משה מעביר?
    # איפה יש TRX?
    #
    # במקרה כזה אסור למזג אוטומטית
    # את הפילטרים מהחיפוש הקודם.
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Explicit follow-up signals
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Short fragments may still be natural follow-ups
    # -----------------------------------------------------
    #
    # למשל:
    # בבוקר
    # במרכז הדס
    # פילאטיס
    # ביום רביעי
    #
    # אבל שאלות מלאות כבר נפסלו למעלה.
    # -----------------------------------------------------

    if len(
        words
    ) <= 4:
        return True

    return False
# ---------------------------------------------------------
# Pagination
# ---------------------------------------------------------
"""
בונה את העמוד הבא של תוצאות החיפוש
ומחזירה את התוצאות יחד עם מצב ההמשך
"""
def _build_page_answer(
    results: list[
        dict[str, Any]
    ],
    offset: int,
) -> tuple[
    str,
    int,
    bool,
]:

    total = len(
        results
    )

    page = results[
        offset:
        offset + PAGE_SIZE
    ]

    if not page:

        return (
            "אין תוצאות נוספות.",
            offset,
            False,
        )

    lines = [
        format_activity_hebrew(
            item
        )
        for item in page
    ]

    next_offset = (
        offset
        + len(
            page
        )
    )

    has_more = (
        next_offset
        < total
    )

    answer_parts: list[str] = []

    if offset > 0:

        answer_parts.append(
            f"מציג תוצאות "
            f"{offset + 1}–{next_offset} "
            f"מתוך {total}:"
        )

    answer_parts.append(
        "\n".join(
            lines
        )
    )

    if has_more:

        remaining = (
            total
            - next_offset
        )

        answer_parts.append(
            f"\nנשארו עוד {remaining} תוצאות. "
            f"רוצה לראות עוד?"
        )

    elif offset > 0:

        answer_parts.append(
            "\nאלה כל התוצאות."
        )

    return (
        "\n".join(
            answer_parts
        ),
        next_offset,
        has_more,
    )


# ---------------------------------------------------------
# User-data helpers
# ---------------------------------------------------------
"""
מאפסת את המידע השמור להצגת תוצאות נוספות
ומחזירה את מצב התצוגה להתחלה
"""
def _reset_pagination(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    context.user_data[
        "pagination_results"
    ] = []

    context.user_data[
        "pagination_offset"
    ] = 0

    context.user_data[
        "waiting_for_more"
    ] = False


def _reset_clarification(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    context.user_data[
        "waiting_for_clarification"
    ] = False

    context.user_data[
        "clarification_state"
    ] = {}


def _reset_search_memory(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    context.user_data[
        "last_search_state"
    ] = {}

    context.user_data[
        "last_search_query"
    ] = ""


def _reset_conversation_state(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    _reset_pagination(
        context
    )

    _reset_clarification(
        context
    )

    _reset_search_memory(
        context
    )


# ---------------------------------------------------------
# Simple replies
# ---------------------------------------------------------
"""
שולחת למשתמש הודעת ברכה
ומציגה את תפריט הפעולות הראשי
"""
async def _reply_greeting(
    update: Update,
) -> None:

    message = (
        update.effective_message
    )

    if message is None:
        return

    await message.reply_text(
        "שלום! 👋\n"
        "אני Community Center AI Agent 🤖.\n"
        "אפשר לכתוב מה מחפשים "
        "או להשתמש בכפתורים למטה.",
        reply_markup=(
            _main_keyboard()
        ),
    )

"""
שולחת תגובה כאשר המשתמש מביע תודה
ומחזירה את תפריט הפעולות הראשי
"""
async def _reply_thanks(
    update: Update,
) -> None:

    message = (
        update.effective_message
    )

    if message is None:
        return

    await message.reply_text(
        "בשמחה! 😊\n"
        "אפשר להמשיך לחיפוש נוסף בכל זמן.",
        reply_markup=(
            _main_keyboard()
        ),
    )


# ---------------------------------------------------------
# Commands
# ---------------------------------------------------------
"""
מטפלת בפקודת ההתחלה של הבוט
מאפסת את מצב השיחה ומציגה את הודעת הפתיחה
"""
async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    message = (
        update.effective_message
    )

    if message is None:
        return

    _reset_conversation_state(
        context
    )

    await message.reply_text(
        START_TEXT,
        reply_markup=(
            _main_keyboard()
        ),
    )

"""
מטפלת בבקשת העזרה של המשתמש
ומציגה הסבר על אפשרויות השימוש בבוט
"""
async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    message = (
        update.effective_message
    )

    if message is None:
        return

    await message.reply_text(
        HELP_TEXT,
        reply_markup=(
            _main_keyboard()
        ),
    )

"""
מאפסת את מצב השיחה והחיפוש של המשתמש
ומאפשרת להתחיל חיפוש חדש
"""
async def reset_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    message = (
        update.effective_message
    )

    if message is None:
        return

    _reset_conversation_state(
        context
    )

    await message.reply_text(
        "השיחה אופסה. 🔄\n"
        "אפשר להתחיל חיפוש חדש.",
        reply_markup=(
            _main_keyboard()
        ),
    )


# ---------------------------------------------------------
# Sticker handler
# ---------------------------------------------------------
"""
מטפלת בקבלת מדבקה מהמשתמש
ומתעלמת ממנה ללא הפעלת תהליך החיפוש
"""
async def handle_sticker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    return


# ---------------------------------------------------------
# Main conversation processor
# תהליך עיבוד הודעת המשתמש
# ---------------------------------------------------------
#
# הודעת משתמש
#      |
#      v
# בדיקות מהירות
#      |
#      v
# טעינת מצב השיחה
#      |
#      v
# בדיקת המשך או הבהרה
#      |
#      v
# בניית הבקשה הסופית
#      |
#      v
# הפעלת הסוכן
#      |
#      v
# שליחת תשובה
#      |
#      v
# שמירת מצב החיפוש

"""
מנהלת את כל תהליך העיבוד של הודעת המשתמש
בודקת את מצב השיחה מטפלת בהמשכים ובהבהרות
מעבירה את הבקשה לסוכן ושומרת את מצב החיפוש החדש
"""
async def _process_user_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:

    message = (
        update.effective_message
    )

    if message is None:
        return

    user_message = (
        user_message.strip()
    )

    if not user_message:
        return

    try:

        # -------------------------------------------------
        # Ignore symbols
        # -------------------------------------------------

        if _is_symbol_only_message(
            user_message
        ):
            return

        # -------------------------------------------------
        # Greeting
        # -------------------------------------------------

        if _is_greeting(
            user_message
        ):

            await _reply_greeting(
                update
            )

            return

        # -------------------------------------------------
        # Thanks
        # -------------------------------------------------

        if _is_thanks(
            user_message
        ):

            _reset_pagination(
                context
            )

            await _reply_thanks(
                update
            )

            return

        # -------------------------------------------------
        # Load state
        # -------------------------------------------------

        waiting_for_more = bool(
            context.user_data.get(
                "waiting_for_more",
                False,
            )
        )

        waiting_for_clarification = bool(
            context.user_data.get(
                "waiting_for_clarification",
                False,
            )
        )

        last_search_state = (
            context.user_data.get(
                "last_search_state",
                {},
            )
        )

        clarification_state = (
            context.user_data.get(
                "clarification_state",
                {},
            )
        )

        # -------------------------------------------------
        # Stop / thanks
        # -------------------------------------------------

        if _looks_like_thanks_or_stop(
            user_message
        ):

            decision = (
                await _classify_conversation_message_async(
                    user_message=
                        user_message,
                    previous_state=
                        last_search_state,
                    waiting_for_more=
                        waiting_for_more,
                    waiting_for_clarification=
                        False,
                )
            )

            if decision.action in {
                "stop",
                "thanks",
            }:

                _reset_pagination(
                    context
                )

                await _reply_thanks(
                    update
                )

                return

        # -------------------------------------------------
        # Pagination
        # -------------------------------------------------

        if waiting_for_more:

            if _is_more_request(
                user_message
            ):

                decision_action = (
                    "more"
                )

            elif _is_stop_more_request(
                user_message
            ):

                decision_action = (
                    "stop"
                )

            else:

                decision = (
                    await _classify_conversation_message_async(
                        user_message=
                            user_message,
                        previous_state=
                            last_search_state,
                        waiting_for_more=
                            True,
                        waiting_for_clarification=
                            False,
                    )
                )

                decision_action = (
                    decision.action
                )

            if decision_action == "more":

                pagination_results = (
                    context.user_data.get(
                        "pagination_results",
                        [],
                    )
                )

                pagination_offset = int(
                    context.user_data.get(
                        "pagination_offset",
                        PAGE_SIZE,
                    )
                )

                (
                    answer,
                    next_offset,
                    has_more,
                ) = (
                    _build_page_answer(
                        results=
                            pagination_results,
                        offset=
                            pagination_offset,
                    )
                )

                await message.reply_text(
                    answer,
                    reply_markup=(
                        _results_keyboard(
                            has_more=
                                has_more
                        )
                    ),
                )

                context.user_data[
                    "pagination_offset"
                ] = next_offset

                context.user_data[
                    "waiting_for_more"
                ] = has_more

                if not has_more:

                    context.user_data[
                        "pagination_results"
                    ] = []

                    context.user_data[
                        "pagination_offset"
                    ] = 0

                return

            if decision_action == "stop":

                _reset_pagination(
                    context
                )

                await message.reply_text(
                    "בסדר. אפשר להמשיך לחיפוש אחר.",
                    reply_markup=(
                        _main_keyboard()
                    ),
                )

                return

            if decision_action == "greeting":

                await _reply_greeting(
                    update
                )

                return

            if decision_action == "thanks":

                _reset_pagination(
                    context
                )

                await _reply_thanks(
                    update
                )

                return

            _reset_pagination(
                context
            )

        # -------------------------------------------------
        # Decide final query
        # -------------------------------------------------

        message_for_graph = (
            user_message
        )

        # -------------------------------------------------
        # Clarification
        # -------------------------------------------------

        if waiting_for_clarification:

            decision = (
                await _classify_conversation_message_async(
                    user_message=
                        user_message,
                    previous_state=
                        clarification_state,
                    waiting_for_more=
                        False,
                    waiting_for_clarification=
                        True,
                )
            )

            if decision.action == "greeting":

                await _reply_greeting(
                    update
                )

                return

            if decision.action == "thanks":

                await _reply_thanks(
                    update
                )

                return

            if (
                decision.action
                == "use_known_filters"
            ):

                if not _has_meaningful_search_filters(
                    clarification_state
                ):

                    await message.reply_text(
                        "כדי לבצע חיפוש צריך לפחות פרט אחד — "
                        "למשל יום, שעה, סוג חוג, "
                        "מרכז או מדריך/ה.",
                        reply_markup=(
                            _clarification_keyboard()
                        ),
                    )

                    return

                message_for_graph = (
                    _build_query_from_state(
                        clarification_state
                    )
                )

            elif (
                decision.action
                == "new_query"
            ):

                _reset_clarification(
                    context
                )

                message_for_graph = (
                    user_message
                )

            else:

                fragment = (
                    decision.query_fragment
                    or user_message
                )

                if (
                    decision.clear_fields
                    and decision.query_fragment
                    is None
                ):

                    fragment = None

                message_for_graph = (
                    await _merge_follow_up_async(
                        previous_state=
                            clarification_state,
                        query_fragment=
                            fragment,
                        clear_fields=
                            decision.clear_fields,
                    )
                )

        # -------------------------------------------------
        # Normal follow-up
        # -------------------------------------------------

        elif (
            last_search_state
            and _should_check_conversation_context(
                user_message,
                last_search_state,
            )
        ):

            decision = (
                await _classify_conversation_message_async(
                    user_message=
                        user_message,
                    previous_state=
                        last_search_state,
                    waiting_for_more=
                        False,
                    waiting_for_clarification=
                        False,
                )
            )

            if decision.action == "greeting":

                await _reply_greeting(
                    update
                )

                return

            if decision.action == "thanks":

                await _reply_thanks(
                    update
                )

                return

            if decision.action == "follow_up":

                fragment = (
                    decision.query_fragment
                    or user_message
                )

                if (
                    decision.clear_fields
                    and decision.query_fragment
                    is None
                ):

                    fragment = None

                message_for_graph = (
                    await _merge_follow_up_async(
                        previous_state=
                            last_search_state,
                        query_fragment=
                            fragment,
                        clear_fields=
                            decision.clear_fields,
                    )
                )

            else:

                message_for_graph = (
                    user_message
                )

        # -------------------------------------------------
        # Graph
        # -------------------------------------------------

        result = (
            await _invoke_graph_async(
                message_for_graph
            )
        )

        final_answer = (
            result.get(
                "final_answer"
            )
        )

        if not final_answer:

            final_answer = (
                "לא הצלחתי ליצור תשובה. "
                "אפשר לנסות לנסח את השאלה מחדש."
            )

        final_answer = (
            _neutralize_response_text(
                final_answer
            )
        )

        # -------------------------------------------------
        # Result metadata
        # -------------------------------------------------

        new_waiting_for_clarification = bool(
            result.get(
                "waiting_for_clarification",
                False,
            )
        )

        tool_results = (
            result.get(
                "tool_results",
                [],
            )
        )

        has_more_results = (
            isinstance(
                tool_results,
                list,
            )
            and len(
                tool_results
            ) > PAGE_SIZE
        )

        # -------------------------------------------------
        # Keyboard
        # -------------------------------------------------

        if new_waiting_for_clarification:

            response_keyboard = (
                _clarification_keyboard()
            )

        else:

            response_keyboard = (
                _results_keyboard(
                    has_more=
                        has_more_results
                )
            )

        # -------------------------------------------------
        # Reply
        # -------------------------------------------------

        await message.reply_text(
            final_answer,
            reply_markup=
                response_keyboard,
        )

        # -------------------------------------------------
        # Clarification state
        # -------------------------------------------------

        context.user_data[
            "waiting_for_clarification"
        ] = (
            new_waiting_for_clarification
        )

        if new_waiting_for_clarification:

            context.user_data[
                "clarification_state"
            ] = dict(
                result
            )

            _reset_pagination(
                context
            )

            return

        context.user_data[
            "clarification_state"
        ] = {}

        # -------------------------------------------------
        # Save search state
        # -------------------------------------------------

        if (
            result.get(
                "intent"
            )
            == "activity"
        ):

            context.user_data[
                "last_search_state"
            ] = dict(
                result
            )

            context.user_data[
                "last_search_query"
            ] = (
                message_for_graph
            )

        # -------------------------------------------------
        # Pagination state
        # -------------------------------------------------

        if has_more_results:

            context.user_data[
                "pagination_results"
            ] = (
                tool_results
            )

            context.user_data[
                "pagination_offset"
            ] = (
                PAGE_SIZE
            )

            context.user_data[
                "waiting_for_more"
            ] = True

        else:

            _reset_pagination(
                context
            )

    except Exception as error:

        print(
            "Telegram message error:",
            repr(
                error
            ),
        )

        await message.reply_text(
            "אירעה שגיאה בזמן עיבוד הבקשה. "
            "אפשר לנסות שוב.",
            reply_markup=(
                _main_keyboard()
            ),
        )


# ---------------------------------------------------------
# Typing indicator
# ---------------------------------------------------------
"""
מחדשת את מצב הכתיבה בזמן שהבקשה מעובדת
כדי שהמשתמש יראה שהבוט עדיין עובד
"""
async def _typing_loop(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """
    מחדש את מצב typing...
    כל כמה שניות כל עוד הסוכן עובד.
    """

    try:

        while True:

            await asyncio.sleep(
                4
            )

            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING,
            )

    except asyncio.CancelledError:
        pass

    except Exception as error:

        print(
            "Typing indicator error:",
            repr(
                error
            ),
        )

"""
מפעילה את עיבוד הודעת המשתמש
ובמקביל מציגה מצב כתיבה עד לסיום העיבוד
"""
async def _process_with_typing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> None:
    """
    מפעיל את עיבוד הבקשה
    תוך הצגת typing...
    לאורך זמן העיבוד.
    """

    chat = (
        update.effective_chat
    )

    if chat is None:

        await _process_user_message(
            update=update,
            context=context,
            user_message=user_message,
        )

        return

    # הצגת typing... מיידית.
    await context.bot.send_chat_action(
        chat_id=chat.id,
        action=ChatAction.TYPING,
    )

    # רענון כל 4 שניות
    # אם העיבוד עדיין לא הסתיים.
    typing_task = asyncio.create_task(
        _typing_loop(
            context=context,
            chat_id=chat.id,
        )
    )

    # נותן ל-event loop הזדמנות
    # להתחיל את משימת ה-typing.
    await asyncio.sleep(
        0
    )

    try:

        await _process_user_message(
            update=update,
            context=context,
            user_message=user_message,
        )

    finally:

        typing_task.cancel()

        try:
            await typing_task

        except asyncio.CancelledError:
            pass

# ---------------------------------------------------------
# זרימת קלט מהמשתמש
# ---------------------------------------------------------
#
# הודעת טקסט ------> handle_message
#                         |
#                         v
#                 תהליך העיבוד הראשי
#
# לחיצה על כפתור --> handle_button
#                         |
#                         v
#                 תהליך העיבוד הראשי


# ---------------------------------------------------------
# Text-message handler
# ---------------------------------------------------------
"""
מקבלת הודעת טקסט מהמשתמש
ומעבירה אותה לתהליך העיבוד הראשי
"""
async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    message = (
        update.effective_message
    )

    if message is None:
        return

    user_message = (
        message.text
        or ""
    ).strip()

    if not user_message:
        return

    await _process_with_typing(
        update=
            update,
        context=
            context,
        user_message=
            user_message,
    )


# ---------------------------------------------------------
# Inline-button handler
# ---------------------------------------------------------
"""
מטפלת בלחיצות על כפתורי הבוט
וממירה כל בחירה להודעה מתאימה להמשך העיבוד
"""
async def handle_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    query = (
        update.callback_query
    )

    if query is None:
        return

    # מפסיק את אנימציית הלחיצה של Telegram.
    await query.answer()

    message = (
        query.message
    )

    if message is None:
        return

    data = (
        query.data
        or ""
    )

    # -----------------------------------------------------
    # Remove old buttons immediately
    # -----------------------------------------------------

    try:

        await query.edit_message_reply_markup(
            reply_markup=None
        )

    except Exception as error:

        print(
            "Could not remove old inline keyboard:",
            repr(
                error
            ),
        )

    # -----------------------------------------------------
    # New search
    # -----------------------------------------------------

    if data == CB_NEW_SEARCH:

        await message.reply_text(
            "🔄 חיפוש חדש"
        )

        _reset_conversation_state(
            context
        )

        await message.reply_text(
            "החיפוש אופס. 🔄\n"
            "אפשר להתחיל חיפוש חדש.",
            reply_markup=(
                _main_keyboard()
            ),
        )

        return

    # -----------------------------------------------------
    # Help
    # -----------------------------------------------------

    if data == CB_HELP:

        await message.reply_text(
            "❓ עזרה"
        )

        await message.reply_text(
            HELP_TEXT,
            reply_markup=(
                _main_keyboard()
            ),
        )

        return

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    if data == CB_SEARCH:

        await message.reply_text(
            "🔎 חיפוש חוגים"
        )

        await message.reply_text(
            "אפשר לכתוב מה מחפשים "
            "בשפה חופשית.\n\n"

            "לדוגמה:\n"
            "• מה יש מחר בערב?\n"
            "• פילאטיס ביום שלישי\n"
            "• מה יש במרכז הדס?\n\n"

            "אפשר גם לבחור יום או זמן "
            "מהכפתורים.",
            reply_markup=(
                _main_keyboard()
            ),
        )

        return

    # -----------------------------------------------------
    # Load conversation context
    # -----------------------------------------------------

    waiting_for_more = bool(
        context.user_data.get(
            "waiting_for_more",
            False,
        )
    )

    waiting_for_clarification = bool(
        context.user_data.get(
            "waiting_for_clarification",
            False,
        )
    )

    last_search_state = (
        context.user_data.get(
            "last_search_state",
            {},
        )
    )

    has_context = (
        waiting_for_clarification
        or bool(
            last_search_state
        )
    )

    # -----------------------------------------------------
    # Translate button to visible + semantic message
    # -----------------------------------------------------

    if data == CB_MORE:

        if not waiting_for_more:

            await message.reply_text(
                "אין כרגע תוצאות נוספות להצגה.",
                reply_markup=(
                    _results_keyboard(
                        has_more=
                            False
                    )
                ),
            )

            return

        display_text = (
            "📄 הצג עוד"
        )

        semantic_message = (
            "עוד"
        )

    elif data == CB_NO_PREFERENCE:

        display_text = (
            "✅ אין לי העדפה"
        )

        semantic_message = (
            "אין לי העדפה"
        )

    elif data == CB_TODAY:

        display_text = (
            "📅 היום"
        )

        if has_context:

            semantic_message = (
                "ומה היום?"
            )

        else:

            semantic_message = (
                "מה יש היום?"
            )

    elif data == CB_TOMORROW:

        display_text = (
            "➡️ מחר"
        )

        if has_context:

            semantic_message = (
                "ומה מחר?"
            )

        else:

            semantic_message = (
                "מה יש מחר?"
            )

    elif data == CB_MORNING:

        display_text = (
            "🌅 בוקר"
        )

        if has_context:

            semantic_message = (
                "ומה בבוקר?"
            )

        else:

            semantic_message = (
                "מה יש בבוקר?"
            )

    elif data == CB_EVENING:

        display_text = (
            "🌆 ערב"
        )

        if has_context:

            semantic_message = (
                "ומה בערב?"
            )

        else:

            semantic_message = (
                "מה יש בערב?"
            )

    else:
        return

    # -----------------------------------------------------
    # Show the selected option
    # -----------------------------------------------------

    await message.reply_text(
        display_text
    )

    # -----------------------------------------------------
    # Same AI flow + typing indicator
    # -----------------------------------------------------

    await _process_with_typing(
        update=
            update,
        context=
            context,
        user_message=
            semantic_message,
    )


# ---------------------------------------------------------
# Error handler
# ---------------------------------------------------------
"""
מטפלת בשגיאות שמתקבלות במהלך עבודת הבוט
ומדפיסה את פרטי השגיאה לצורך בדיקה
"""
async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    print(
        "Telegram error:",
        repr(
            context.error
        ),
    )


# ---------------------------------------------------------
# Application
# ---------------------------------------------------------
"""
בונה את אפליקציית הטלגרם
ומחברת את הפקודות ההודעות והכפתורים לפונקציות המתאימות
"""
def build_application() -> Application:

    token = (
        _get_bot_token()
    )

    application = (
        Application
        .builder()
        .token(
            token
        )
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "reset",
            reset_command,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            handle_button
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.Sticker.ALL,
            handle_sticker,
        )
    )

    application.add_error_handler(
        error_handler
    )

    return application


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
"""
מפעילה את אפליקציית הטלגרם
ומתחילה להאזין לעדכונים חדשים מהמשתמשים
"""
def main() -> None:

    print(
        "Starting Telegram bot..."
    )

    application = (
        build_application()
    )

    print(
        "Telegram bot is running."
    )

    print(
        "Press Ctrl+C to stop."
    )

    application.run_polling(
        allowed_updates=
            Update.ALL_TYPES
    )


if __name__ == "__main__":

    main()
from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
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
# ממשק טלגרם
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
    rows: list[list[InlineKeyboardButton]] = []

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

    return InlineKeyboardMarkup(rows)


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
# משתני סביבה
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


# ---------------------------------------------------------
# כלי עזר לטקסט
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
    stripped = text.strip()

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
# כללים מהירים וקבועים
# ---------------------------------------------------------

"""
בודקת האם הודעת המשתמש היא ברכה מוכרת
כדי לאפשר תגובה ישירה ללא הפעלת הסוכן
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

    return normalized in greetings


"""
בודקת האם הודעת המשתמש היא הודעת תודה מוכרת
כדי לאפשר תגובה ישירה ללא הפעלת הסוכן
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

    return normalized in thanks_messages


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
        "תראה עוד",
        "תראי עוד",
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
בודקת האם המשתמש מבקש לעצור את הצגת התוצאות הנוספות
בלי לפרש בטעות שינוי של תנאי חיפוש כבקשת עצירה
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

    stop_answers = {
        "לא",
        "לא תודה",
        "לא צריך",
        "לא צריך תודה",
        "מספיק",
        "זה מספיק",
        "מספיק תודה",
        "תודה זה מספיק",
        "סיימתי",
    }

    return normalized in stop_answers


# ---------------------------------------------------------
# זיכרון שיחה בטלגרם
# ---------------------------------------------------------

"""
בונה מזהה שיחה ייחודי לפי המשתמש והשיחה בטלגרם
כדי שלנגרף ישמור זיכרון נפרד לכל שיחה פעילה
"""
def _get_conversation_thread_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    chat = update.effective_chat
    user = update.effective_user

    chat_id = (
        chat.id
        if chat is not None
        else 0
    )

    user_id = (
        user.id
        if user is not None
        else 0
    )

    generation = int(
        context.user_data.get(
            "memory_thread_generation",
            0,
        )
    )

    return (
        f"telegram:"
        f"{chat_id}:"
        f"{user_id}:"
        f"{generation}"
    )


"""
מאפסת את מצב התצוגה של התוצאות הנוספות
ומחזירה את החלוקה לעמודים להתחלה
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


"""
מאפסת את מצב השיחה המקומי של טלגרם
ופותחת זיכרון חדש בלנגרף לחיפוש הבא
"""
def _reset_conversation_state(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    _reset_pagination(
        context
    )

    context.user_data[
        "has_active_context"
    ] = False

    context.user_data[
        "waiting_for_clarification"
    ] = False

    current_generation = int(
        context.user_data.get(
            "memory_thread_generation",
            0,
        )
    )

    context.user_data[
        "memory_thread_generation"
    ] = (
        current_generation
        + 1
    )


# ---------------------------------------------------------
# חלוקת התוצאות לעמודים
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
# הפעלת הגרף
# ---------------------------------------------------------

"""
מפעילה את הסוכן עם מזהה השיחה המתאים
כדי שלנגרף יטען את הזיכרון הקודם וישמור את המצב החדש
"""
async def _invoke_graph_async(
    user_message: str,
    thread_id: str,
) -> dict[str, Any]:
    config = {
        "configurable": {
            "thread_id":
                thread_id,
        }
    }

    return await asyncio.to_thread(
        graph.invoke,
        {
            "user_message":
                user_message,
        },
        config,
    )


# ---------------------------------------------------------
# תגובות פשוטות
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
# פקודות
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
ומאפשרת להתחיל חיפוש חדש ללא הזיכרון הקודם
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
# טיפול במדבקות
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
# תהליך עיבוד הודעת המשתמש
# ---------------------------------------------------------
#
# הודעת המשתמש
#      ↓
# בדיקות פשוטות של טלגרם
#      ↓
# טיפול בהצגת תוצאות נוספות אם נדרש
#      ↓
# שליחת ההודעה המקורית ללנגרף
#      ↓
# לנגרף מנהל את ההקשר ואת זיכרון השיחה
#      ↓
# טלגרם מציג את התשובה והכפתורים


"""
מעבירה את הודעת המשתמש לסוכן
ומשאירה את הבנת השיחה ואת מיזוג ההמשכים בתוך לנגרף בלבד
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
        # התעלמות מהודעות שמכילות רק סימנים
        # -------------------------------------------------

        if _is_symbol_only_message(
            user_message
        ):
            return

        # -------------------------------------------------
        # ברכה
        # -------------------------------------------------

        if _is_greeting(
            user_message
        ):
            await _reply_greeting(
                update
            )
            return

        # -------------------------------------------------
        # תודה
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
        # תוצאות נוספות
        # -------------------------------------------------

        waiting_for_more = bool(
            context.user_data.get(
                "waiting_for_more",
                False,
            )
        )

        if waiting_for_more:

            if _is_more_request(
                user_message
            ):
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

            if _is_stop_more_request(
                user_message
            ):
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

            _reset_pagination(
                context
            )

        # -------------------------------------------------
        # הפעלת לנגרף עם ההודעה המקורית
        # -------------------------------------------------

        thread_id = (
            _get_conversation_thread_id(
                update=
                    update,
                context=
                    context,
            )
        )

        result = (
            await _invoke_graph_async(
                user_message=
                    user_message,
                thread_id=
                    thread_id,
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
        # נתוני התוצאה
        # -------------------------------------------------

        waiting_for_clarification = bool(
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
        # בחירת תפריט הכפתורים
        # -------------------------------------------------

        if waiting_for_clarification:
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
        # שליחת התשובה
        # -------------------------------------------------

        await message.reply_text(
            final_answer,
            reply_markup=
                response_keyboard,
        )

        # -------------------------------------------------
        # שמירת מצב תצוגה בלבד
        # -------------------------------------------------

        context.user_data[
            "waiting_for_clarification"
        ] = (
            waiting_for_clarification
        )

        context.user_data[
            "has_active_context"
        ] = bool(
            waiting_for_clarification
            or result.get(
                "intent"
            ) == "activity"
        )

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
# חיווי כתיבה
# ---------------------------------------------------------

"""
מחדשת את מצב הכתיבה בזמן שהבקשה מעובדת
כדי שהמשתמש יראה שהבוט עדיין עובד
"""
async def _typing_loop(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    try:
        while True:
            await asyncio.sleep(
                4
            )

            await context.bot.send_chat_action(
                chat_id=
                    chat_id,
                action=
                    ChatAction.TYPING,
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
    chat = (
        update.effective_chat
    )

    if chat is None:
        await _process_user_message(
            update=
                update,
            context=
                context,
            user_message=
                user_message,
        )
        return

    await context.bot.send_chat_action(
        chat_id=
            chat.id,
        action=
            ChatAction.TYPING,
    )

    typing_task = (
        asyncio.create_task(
            _typing_loop(
                context=
                    context,
                chat_id=
                    chat.id,
            )
        )
    )

    await asyncio.sleep(
        0
    )

    try:
        await _process_user_message(
            update=
                update,
            context=
                context,
            user_message=
                user_message,
        )

    finally:
        typing_task.cancel()

        try:
            await typing_task

        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------
# טיפול בהודעות טקסט
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
# טיפול בלחיצות על כפתורים
# ---------------------------------------------------------

"""
מטפלת בלחיצות על כפתורי הבוט
וממירה כל בחירה להודעה טבעית שמתאימה למצב השיחה
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
    # הסרת הכפתורים הישנים
    # -----------------------------------------------------

    try:
        await query.edit_message_reply_markup(
            reply_markup=
                None
        )

    except Exception as error:
        print(
            "Could not remove old inline keyboard:",
            repr(
                error
            ),
        )

    # -----------------------------------------------------
    # חיפוש חדש
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
    # עזרה
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
    # חיפוש
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
    # קביעת משמעות הכפתור
    # -----------------------------------------------------

    has_context = bool(
        context.user_data.get(
            "has_active_context",
            False,
        )
    )

    waiting_for_more = bool(
        context.user_data.get(
            "waiting_for_more",
            False,
        )
    )

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

        semantic_message = (
            "ומה היום?"
            if has_context
            else "מה יש היום?"
        )

    elif data == CB_TOMORROW:
        display_text = (
            "➡️ מחר"
        )

        semantic_message = (
            "ומה מחר?"
            if has_context
            else "מה יש מחר?"
        )

    elif data == CB_MORNING:
        display_text = (
            "🌅 בוקר"
        )

        semantic_message = (
            "ומה בבוקר?"
            if has_context
            else "מה יש בבוקר?"
        )

    elif data == CB_EVENING:
        display_text = (
            "🌆 ערב"
        )

        semantic_message = (
            "ומה בערב?"
            if has_context
            else "מה יש בערב?"
        )

    else:
        return

    # -----------------------------------------------------
    # הצגת הבחירה והמשך העיבוד
    # -----------------------------------------------------

    await message.reply_text(
        display_text
    )

    await _process_with_typing(
        update=
            update,
        context=
            context,
        user_message=
            semantic_message,
    )


# ---------------------------------------------------------
# טיפול בשגיאות
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
# בניית היישום
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
# הפעלה ראשית
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
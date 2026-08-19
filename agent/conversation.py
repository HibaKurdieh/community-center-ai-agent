from __future__ import annotations

import sys
from typing import Any

from graph import graph
from tools import format_activity_hebrew


PAGE_SIZE = 5


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
# Text helpers
# ---------------------------------------------------------

def _normalize_text(
    text: str,
) -> str:
    return " ".join(
        text.strip().casefold().split()
    )


def _is_more_request(
    text: str,
) -> bool:
    """
    מזהה בקשה להצגת תוצאות נוספות.
    """

    normalized = _normalize_text(
        text
    )

    normalized = normalized.strip(
        "?!.,:;׳״\"'"
    )

    positive_answers = {
        "כן",
        "כן בבקשה",
        "בטח",
        "בטח שכן",
        "יאללה",
        "בסדר",
        "אוקיי",
        "אוקי",
        "אפשר",
        "אפשר בבקשה",
    }

    if normalized in positive_answers:
        return True

    # בקשות טבעיות כמו:
    # אפשר עוד?
    # יש עוד?
    # תראה עוד
    if "עוד" in normalized:
        return True

    return False


def _is_stop_more_request(
    text: str,
) -> bool:
    """
    מזהה שהמשתמש לא רוצה תוצאות נוספות.
    """

    normalized = _normalize_text(
        text
    )

    normalized = normalized.strip(
        "?!.,:;׳״\"'"
    )

    stop_phrases = {
        "לא",
        "לא תודה",
        "מספיק",
        "זה מספיק",
        "לא צריך",
        "לא צריך עוד",
        "עזוב",
        "עזבי",
        "סיימתי",
        "תודה",
        "תודה רבה",
    }

    if normalized in stop_phrases:
        return True

    if (
        normalized.startswith("לא ")
        and "עוד" in normalized
    ):
        return True

    return False


# ---------------------------------------------------------
# Result formatting
# ---------------------------------------------------------

def _format_result(
    item: dict[str, Any],
) -> str:
    """
    מציג תוצאת חוג אחת.
    """

    return format_activity_hebrew(
        item
    )


def _build_page_answer(
    results: list[dict[str, Any]],
    offset: int,
) -> tuple[str, int, bool]:
    """
    בונה עמוד אחד של תוצאות.

    Returns:
    - answer
    - next_offset
    - has_more
    """

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
        _format_result(
            item
        )
        for item in page
    ]

    next_offset = (
        offset
        + len(page)
    )

    has_more = (
        next_offset
        < total
    )

    answer_parts: list[str] = []

    if offset > 0:
        start_number = (
            offset + 1
        )

        end_number = (
            next_offset
        )

        answer_parts.append(
            f"מציג תוצאות "
            f"{start_number}–{end_number} "
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
# Clarification helpers
# ---------------------------------------------------------

SEARCH_FIELDS = [
    "age",
    "category",
    "target_audience",
    "day",
    "start_after",
    "start_before",
    "location",
    "center_name",
    "branch",
    "instructor",
]


def _build_context_message(
    previous_state: dict[str, Any],
    new_message: str,
) -> str:
    """
    משלב את תשובת המשתמש עם המידע
    שכבר הובן בסבב הקודם.

    לדוגמה:

    קודם:
    יום רביעי בערב

    עכשיו:
    יוגה

    נשלח ל-Graph:
    "יוגה ביום רביעי בערב"
    """

    context_parts: list[str] = []

    day = previous_state.get(
        "day"
    )

    if day:
        context_parts.append(
            f"ביום {day}"
        )

    start_after = previous_state.get(
        "start_after"
    )

    start_before = previous_state.get(
        "start_before"
    )

    if (
        start_after == "17:00"
        and start_before == "23:59"
    ):
        context_parts.append(
            "בערב"
        )

    elif (
        start_after == "06:00"
        and start_before == "12:00"
    ):
        context_parts.append(
            "בבוקר"
        )

    elif (
        start_after == "12:00"
        and start_before == "17:00"
    ):
        context_parts.append(
            "בצהריים"
        )

    elif start_after:
        context_parts.append(
            f"אחרי {start_after}"
        )

    elif start_before:
        context_parts.append(
            f"לפני {start_before}"
        )

    center_name = previous_state.get(
        "center_name"
    )

    if center_name:
        context_parts.append(
            f"במרכז {center_name}"
        )

    branch = previous_state.get(
        "branch"
    )

    if branch:
        context_parts.append(
            f"בסניף {branch}"
        )

    location = previous_state.get(
        "location"
    )

    if location:
        context_parts.append(
            f"במיקום {location}"
        )

    instructor = previous_state.get(
        "instructor"
    )

    if instructor:
        context_parts.append(
            f"עם המדריך {instructor}"
        )

    target_audience = previous_state.get(
        "target_audience"
    )

    if target_audience:
        context_parts.append(
            f"לקהל {target_audience}"
        )

    age = previous_state.get(
        "age"
    )

    if age is not None:
        context_parts.append(
            f"לגיל {age}"
        )

    if context_parts:
        context = " ".join(
            context_parts
        )

        return (
            f"{new_message} {context}"
        )

    return new_message


# ---------------------------------------------------------
# Conversation
# ---------------------------------------------------------

def run_conversation() -> None:
    """
    מריץ שיחה אינטראקטיבית
    עם סוכן החוגים.
    """

    _ensure_utf8_stdout()

    print(
        "\n=== Community Center AI Agent ==="
    )

    print(
        "אפשר לשאול על חוגים ופעילויות "
        "במרכזי הספורט."
    )

    print(
        "להפסקה כתבו: exit"
    )

    # -----------------------------------------------------
    # Conversation memory
    # -----------------------------------------------------

    previous_state: dict[
        str,
        Any,
    ] = {}

    waiting_for_clarification = False

    # -----------------------------------------------------
    # Pagination memory
    # -----------------------------------------------------

    pagination_results: list[
        dict[str, Any]
    ] = []

    pagination_offset = 0

    waiting_for_more = False

    # -----------------------------------------------------
    # Main loop
    # -----------------------------------------------------

    while True:

        try:
            user_message = input(
                "\nאת: "
            ).strip()

        except (
            EOFError,
            KeyboardInterrupt,
        ):
            print(
                "\nלהתראות!"
            )
            break

        if not user_message:
            continue

        if (
            user_message.casefold()
            in {
                "exit",
                "quit",
                "יציאה",
                "להתראות",
            }
        ):
            print(
                "\nהסוכן:"
            )

            print(
                "להתראות!"
            )

            break

        # -------------------------------------------------
        # Pagination follow-up
        # -------------------------------------------------

        if waiting_for_more:

            if _is_more_request(
                user_message
            ):
                (
                    answer,
                    pagination_offset,
                    waiting_for_more,
                ) = _build_page_answer(
                    results=pagination_results,
                    offset=pagination_offset,
                )

                print(
                    "\nהסוכן:"
                )

                print(
                    answer
                )

                if not waiting_for_more:
                    pagination_results = []
                    pagination_offset = 0

                continue

            if _is_stop_more_request(
                user_message
            ):
                waiting_for_more = False

                pagination_results = []
                pagination_offset = 0

                print(
                    "\nהסוכן:"
                )

                print(
                    "בשמחה. אפשר לשאול משהו נוסף."
                )

                continue

            # המשתמש כתב שאלה חדשה.
            waiting_for_more = False

            pagination_results = []
            pagination_offset = 0

        # -------------------------------------------------
        # Clarification follow-up
        # -------------------------------------------------

        message_for_graph = (
            user_message
        )

        if waiting_for_clarification:

            message_for_graph = (
                _build_context_message(
                    previous_state,
                    user_message,
                )
            )

        # -------------------------------------------------
        # Graph invocation
        # -------------------------------------------------

        result = graph.invoke(
            {
                "user_message":
                    message_for_graph,
            }
        )

        # -------------------------------------------------
        # Preserve known filters after clarification
        # -------------------------------------------------

        if waiting_for_clarification:

            preserved_values: dict[
                str,
                Any,
            ] = {}

            for field in SEARCH_FIELDS:

                current_value = (
                    result.get(
                        field
                    )
                )

                previous_value = (
                    previous_state.get(
                        field
                    )
                )

                if (
                    current_value is None
                    and previous_value is not None
                ):
                    preserved_values[
                        field
                    ] = previous_value

            # אם באמת היה מידע קודם שה-parser
            # לא שחזר, בונים שוב הודעה מלאה.
            if preserved_values:

                reconstructed_state = dict(
                    previous_state
                )

                reconstructed_state.update(
                    result
                )

                reconstructed_state.update(
                    preserved_values
                )

                reconstructed_message = (
                    _build_context_message(
                        reconstructed_state,
                        user_message,
                    )
                )

                result = graph.invoke(
                    {
                        "user_message":
                            reconstructed_message,
                    }
                )

        # -------------------------------------------------
        # Print answer
        # -------------------------------------------------

        print(
            "\nהסוכן:"
        )

        print(
            result.get(
                "final_answer",
                "",
            )
        )

        # -------------------------------------------------
        # Clarification handling
        # -------------------------------------------------

        waiting_for_clarification = bool(
            result.get(
                "waiting_for_clarification",
                False,
            )
        )

        if waiting_for_clarification:

            previous_state = dict(
                result
            )

            print(
                "\n[מחכה להבהרה]"
            )

            continue

        previous_state = dict(
            result
        )

        # -------------------------------------------------
        # Pagination setup
        # -------------------------------------------------

        tool_results = result.get(
            "tool_results",
            [],
        )

        if (
            isinstance(
                tool_results,
                list,
            )
            and len(
                tool_results
            ) > PAGE_SIZE
        ):
            pagination_results = (
                tool_results
            )

            # graph.py כבר הציג את 5 הראשונות.
            pagination_offset = (
                PAGE_SIZE
            )

            waiting_for_more = True

        else:
            pagination_results = []

            pagination_offset = 0

            waiting_for_more = False


if __name__ == "__main__":
    run_conversation()
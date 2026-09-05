from __future__ import annotations

import atexit
import os
import sys
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from conversation import (
    build_query_from_state,
    classify_conversation_message,
    has_meaningful_search_filters,
    merge_follow_up,
    should_check_conversation_context,
)
from request_parser import (
    parse_user_request,
    reinterpret_unclear_request,
)
from state import AgentState
from tools import (
    format_activity_hebrew,
    search_activities,
)


load_dotenv()

RESULT_LIMIT = 5


# ---------------------------------------------------------
# זיכרון קבוע של השיחה
# ---------------------------------------------------------

"""
קוראת את כתובת החיבור למסד הנתונים
ומוודאת שהיא קיימת לפני בניית זיכרון השיחה
"""
def _get_database_url() -> str:
    database_url = os.getenv(
        "DATABASE_URL"
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL לא נמצא "
            "יש לבדוק את קובץ .env"
        )

    return database_url


"""
בונה מאגר חיבורים קבוע למסד הנתונים
כדי לאפשר ללנגרף לשמור את זיכרון השיחה בצורה יציבה
"""
def _build_database_pool() -> ConnectionPool:
    pool = ConnectionPool(
        conninfo=
            _get_database_url(),
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=True,
    )

    pool.wait()

    return pool


os.environ.setdefault(
    "LANGGRAPH_STRICT_MSGPACK",
    "true",
)

database_pool = (
    _build_database_pool()
)

atexit.register(
    database_pool.close
)

checkpointer = PostgresSaver(
    database_pool
)

checkpointer.setup()


"""
מוחקת את כל הזיכרון השמור של שיחה מסוימת
כדי לאפשר התחלה חדשה באמת גם לאחר הפעלה מחדש של הבוט
"""
def delete_conversation_thread(
    thread_id: str,
) -> None:
    clean_thread_id = (
        thread_id.strip()
    )

    if not clean_thread_id:
        return

    checkpointer.delete_thread(
        clean_thread_id
    )


# ---------------------------------------------------------
# הכנת הודעה לפי זיכרון השיחה
# ---------------------------------------------------------

"""
בודקת אם ההודעה החדשה היא המשך של חיפוש קודם
ומשלבת אותה עם המידע שנשמר בזיכרון כאשר נדרש
"""
def prepare_conversation_request(
    state: AgentState,
) -> dict:

    user_message = (
        state.get(
            "user_message",
            "",
        ).strip()
    )

    if not user_message:
        return {
            "conversation_action":
                "new_query",
            "query_fragment":
                None,
            "clear_fields":
                [],
        }

    previous_state = dict(
        state
    )

    waiting_for_clarification = bool(
        state.get(
            "waiting_for_clarification",
            False,
        )
    )

    has_previous_filters = (
        has_meaningful_search_filters(
            previous_state
        )
    )

    if waiting_for_clarification:

        decision = (
            classify_conversation_message(
                user_message=
                    user_message,
                previous_state=
                    previous_state,
                waiting_for_more=
                    False,
                waiting_for_clarification=
                    True,
            )
        )

        if (
            decision.action
            == "use_known_filters"
            and has_previous_filters
        ):

            return {
                "user_message":
                    build_query_from_state(
                        previous_state
                    ),
                "conversation_action":
                    "use_known_filters",
                "query_fragment":
                    None,
                "clear_fields":
                    [],
            }

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

            merged_query = (
                merge_follow_up(
                    previous_state=
                        previous_state,
                    query_fragment=
                        fragment,
                    clear_fields=
                        list(
                            decision.clear_fields
                        ),
                )
            )

            return {
                "user_message":
                    merged_query,
                "conversation_action":
                    "follow_up",
                "query_fragment":
                    decision.query_fragment,
                "clear_fields":
                    list(
                        decision.clear_fields
                    ),
            }

        return {
            "conversation_action":
                decision.action,
            "query_fragment":
                decision.query_fragment,
            "clear_fields":
                list(
                    decision.clear_fields
                ),
        }

    if (
        has_previous_filters
        and should_check_conversation_context(
            user_message,
            previous_state,
        )
    ):

        decision = (
            classify_conversation_message(
                user_message=
                    user_message,
                previous_state=
                    previous_state,
                waiting_for_more=
                    False,
                waiting_for_clarification=
                    False,
            )
        )

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

            merged_query = (
                merge_follow_up(
                    previous_state=
                        previous_state,
                    query_fragment=
                        fragment,
                    clear_fields=
                        list(
                            decision.clear_fields
                        ),
                )
            )

            return {
                "user_message":
                    merged_query,
                "conversation_action":
                    "follow_up",
                "query_fragment":
                    decision.query_fragment,
                "clear_fields":
                    list(
                        decision.clear_fields
                    ),
            }

        return {
            "conversation_action":
                decision.action,
            "query_fragment":
                decision.query_fragment,
            "clear_fields":
                list(
                    decision.clear_fields
                ),
        }

    return {
        "conversation_action":
            "new_query",
        "query_fragment":
            None,
        "clear_fields":
            [],
    }


# ---------------------------------------------------------
# ניתוח בקשת המשתמש
# ---------------------------------------------------------

"""
מנתחת את בקשת המשתמש
ומחלצת ממנה את פרטי החיפוש למצב המשותף
"""
def understand_request(
    state: AgentState,
) -> dict:
    """
    מנתח את בקשת המשתמש באמצעות מודל השפה

    אם הבקשה ברורה
    ממשיכים לחיפוש

    אם הבקשה אינה ברורה
    הגרף יעביר אותה לשלב ניסיון ההבנה הנוסף
    """

    user_message = (
        state.get(
            "user_message",
            "",
        ).strip()
    )

    if not user_message:
        return {
            "intent": "unknown",
            "interpretation_confident": False,
            "fallback_attempted": False,
            "waiting_for_clarification": True,
            "missing_information": [
                "user_message"
            ],
            "clarification_question": (
                "לא התקבלה בקשה. "
                "אפשר לכתוב איזה חוג או פעילות לחפש?"
            ),
            "tool_results": [],
            "final_answer": (
                "לא התקבלה בקשה. "
                "אפשר לכתוב איזה חוג או פעילות לחפש?"
            ),
        }

    parsed = parse_user_request(
        user_message
    )

    return {
        "intent": parsed.intent,
        "interpretation_confident":
            parsed.interpretation_confident,
        "fallback_attempted": False,

        "age": parsed.age,
        "category": parsed.category,
        "target_audience":
            parsed.target_audience,
        "day": parsed.day,
        "start_after":
            parsed.start_after,
        "start_before":
            parsed.start_before,
        "location": parsed.location,
        "center_name":
            parsed.center_name,
        "branch": parsed.branch,
        "instructor":
            parsed.instructor,

        "waiting_for_clarification":
            False,
        "missing_information": [],
        "clarification_question":
            None,
    }


# ---------------------------------------------------------
# החלטה לאחר הניתוח הראשוני
# ---------------------------------------------------------

"""
מחליטה לאיזה שלב להמשיך לאחר הניתוח הראשוני
לפי סוג הבקשה ורמת הביטחון בהבנה
"""
def route_after_understanding(
    state: AgentState,
) -> Literal[
    "activity_node",
    "fallback_node",
    "clarification_node",
]:
    """
    מחליט האם אפשר כבר לחפש
    האם צריך ניסיון הבנה נוסף
    או האם כבר קיימת בקשת הבהרה
    """

    if state.get(
        "waiting_for_clarification",
        False,
    ):
        return "clarification_node"

    intent = state.get(
        "intent",
        "unknown",
    )

    confident = bool(
        state.get(
            "interpretation_confident",
            False,
        )
    )

    if (
        intent == "activity"
        and confident
    ):
        return "activity_node"

    return "fallback_node"


# ---------------------------------------------------------
# ניסיון הבנה נוסף
# ---------------------------------------------------------

"""
מבצעת ניסיון נוסף להבין בקשה שלא הובנה מספיק
ושומרת מידע שכבר זוהה בניתוח הראשון
"""
def fallback_node(
    state: AgentState,
) -> dict:

    user_message = (
        state.get(
            "user_message",
            "",
        ).strip()
    )

    parsed = reinterpret_unclear_request(
        user_message
    )

    return {
        "intent": parsed.intent,
        "interpretation_confident":
            parsed.interpretation_confident,
        "fallback_attempted": True,

        "age": (
            parsed.age
            if parsed.age is not None
            else state.get("age")
        ),

        "category": (
            parsed.category
            if parsed.category is not None
            else state.get("category")
        ),

        "target_audience": (
            parsed.target_audience
            if parsed.target_audience is not None
            else state.get("target_audience")
        ),

        "day": (
            parsed.day
            if parsed.day is not None
            else state.get("day")
        ),

        "start_after": (
            parsed.start_after
            if parsed.start_after is not None
            else state.get("start_after")
        ),

        "start_before": (
            parsed.start_before
            if parsed.start_before is not None
            else state.get("start_before")
        ),

        "location": (
            parsed.location
            if parsed.location is not None
            else state.get("location")
        ),

        "center_name": (
            parsed.center_name
            if parsed.center_name is not None
            else state.get("center_name")
        ),

        "branch": (
            parsed.branch
            if parsed.branch is not None
            else state.get("branch")
        ),

        "instructor": (
            parsed.instructor
            if parsed.instructor is not None
            else state.get("instructor")
        ),
    }


# ---------------------------------------------------------
# החלטה לאחר ניסיון ההבנה הנוסף
# ---------------------------------------------------------

"""
מחליטה כיצד להמשיך לאחר ניסיון ההבנה הנוסף
אם הבקשה ברורה ממשיכים לחיפוש אחרת מבקשים הבהרה
"""
def route_after_fallback(
    state: AgentState,
) -> Literal[
    "activity_node",
    "clarification_node",
]:
    """
    אם ניסיון ההבנה הנוסף הצליח להבין את הבקשה
    ממשיכים לחיפוש

    אחרת מבקשים הבהרה מהמשתמש
    """

    intent = state.get(
        "intent",
        "unknown",
    )

    confident = bool(
        state.get(
            "interpretation_confident",
            False,
        )
    )

    if (
        intent == "activity"
        and confident
    ):
        return "activity_node"

    return "clarification_node"


# ---------------------------------------------------------
# בקשת הבהרה
# ---------------------------------------------------------

"""
בונה שאלת הבהרה כאשר אין מספיק מידע לחיפוש
ושומרת את הפרטים שכבר הובנו מהבקשה
"""
def clarification_node(
    state: AgentState,
) -> dict:
    known_parts: list[str] = []

    # -----------------------------------------------------
    # יום
    # -----------------------------------------------------

    day = state.get(
        "day"
    )

    if day:
        known_parts.append(
            f"ביום {day}"
        )

    # -----------------------------------------------------
    # זמן
    # -----------------------------------------------------

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
        known_parts.append(
            "בערב"
        )

    elif (
        start_after == "21:00"
        and start_before == "23:59"
    ):
        known_parts.append(
            "בלילה"
        )

    elif (
        start_after == "06:00"
        and start_before == "12:00"
    ):
        known_parts.append(
            "בבוקר"
        )

    elif (
        start_after == "12:00"
        and start_before == "17:00"
    ):
        known_parts.append(
            "בצהריים"
        )

    elif (
        start_after
        and start_before
        and start_after == start_before
    ):
        known_parts.append(
            f"בשעה {start_after}"
        )

    elif start_after:
        known_parts.append(
            f"אחרי {start_after}"
        )

    elif start_before:
        known_parts.append(
            f"לפני {start_before}"
        )

    # -----------------------------------------------------
    # מרכז
    # -----------------------------------------------------

    center_name = state.get(
        "center_name"
    )

    if center_name:
        known_parts.append(
            f"במרכז {center_name}"
        )

    # -----------------------------------------------------
    # סניף
    # -----------------------------------------------------

    branch = state.get(
        "branch"
    )

    if branch:
        known_parts.append(
            f"בסניף {branch}"
        )

    # -----------------------------------------------------
    # מדריך
    # -----------------------------------------------------

    instructor = state.get(
        "instructor"
    )

    if instructor:
        known_parts.append(
            f"עם המדריך/ה {instructor}"
        )

    # -----------------------------------------------------
    # מיקום
    # -----------------------------------------------------

    location = state.get(
        "location"
    )

    if location:
        known_parts.append(
            f"במיקום {location}"
        )

    # -----------------------------------------------------
    # קהל יעד
    # -----------------------------------------------------

    target_audience = state.get(
        "target_audience"
    )

    if target_audience:
        known_parts.append(
            f"לקהל {target_audience}"
        )

    # -----------------------------------------------------
    # גיל
    # -----------------------------------------------------

    age = state.get(
        "age"
    )

    if age is not None:
        known_parts.append(
            f"לגיל {age}"
        )

    # -----------------------------------------------------
    # בניית שאלת ההבהרה
    # -----------------------------------------------------

    if known_parts:
        known_text = " ".join(
            known_parts
        )

        question = (
            f"הבנתי שמחפשים פעילות {known_text}, "
            f"אבל עדיין חסר מידע כדי למקד את החיפוש. "
            f"אפשר לכתוב סוג חוג, מרכז, מדריך/ה "
            f"או מיקום. אם אין העדפה נוספת, "
            f"אפשר גם לציין זאת."
        )

    else:
        question = (
            "לא הצלחתי להבין מספיק כדי למקד את החיפוש. "
            "אפשר לציין יום, שעה, מרכז, מדריך/ה, "
            "מיקום או סוג חוג."
        )

    return {
        "missing_information": [
            "search_details"
        ],
        "clarification_question":
            question,
        "waiting_for_clarification":
            True,
        "tool_results": [],
        "final_answer":
            question,
    }


# ---------------------------------------------------------
# פונקציות עזר להתאמת גיל
# ---------------------------------------------------------

"""
סופרת את תוצאות החיפוש לפי רמת הוודאות של התאמת הגיל
ומבדילה בין התאמה ידועה לבין מידע גיל חסר
"""
def _count_age_statuses(
    results: list[dict],
) -> tuple[int, int]:

    match_count = sum(
        1
        for activity in results
        if activity.get(
            "_age_match_status"
        ) == "match"
    )

    unknown_count = sum(
        1
        for activity in results
        if activity.get(
            "_age_match_status"
        ) == "unknown"
    )

    return (
        match_count,
        unknown_count,
    )


"""
בונה הסבר למשתמש כאשר החיפוש כולל גיל
ומבהירה אילו תוצאות מאומתות ואילו חסרות מידע גיל
"""
def _activity_age_summary(
    state: AgentState,
    results: list[dict],
) -> str | None:
    """
    בונה הסבר ברור כאשר המשתמש ציין גיל

    כאשר קיים מידע גיל במקור
    אפשר לאשר התאמה

    כאשר אין טווח גיל במקור
    אי אפשר לאשר התאמה

    תוצאות שאינן מתאימות לגיל
    כבר נפסלות בתוך פעולת החיפוש
    """

    requested_age = state.get(
        "age"
    )

    if requested_age is None:
        return None

    (
        match_count,
        unknown_count,
    ) = _count_age_statuses(
        results
    )

    # -----------------------------------------------------
    # כל התוצאות כוללות התאמת גיל מפורשת
    # -----------------------------------------------------

    if (
        match_count > 0
        and unknown_count == 0
    ):

        if match_count == 1:
            return (
                f"נמצאה התאמה אחת עם מידע גיל מפורש "
                f"שמתאימה לגיל {requested_age}."
            )

        return (
            f"נמצאו {match_count} חוגים עם מידע גיל מפורש "
            f"שמתאים לגיל {requested_age}."
        )

    # -----------------------------------------------------
    # קיימות התאמות מפורשות וגם תוצאות ללא מידע גיל
    # -----------------------------------------------------

    if (
        match_count > 0
        and unknown_count > 0
    ):

        if match_count == 1:
            first_part = (
                f"נמצאה התאמה אחת עם מידע גיל מפורש "
                f"שמתאימה לגיל {requested_age}."
            )

        else:
            first_part = (
                f"נמצאו {match_count} חוגים עם מידע גיל מפורש "
                f"שמתאים לגיל {requested_age}."
            )

        second_part = (
            f"בנוסף קיימים {unknown_count} חוגים שעונים "
            f"לשאר תנאי החיפוש, אבל לא צוין עבורם "
            f"טווח גיל במקור, ולכן אי אפשר לאשר "
            f"בוודאות את התאמתם לגיל {requested_age}."
        )

        return (
            first_part
            + "\n"
            + second_part
        )

    # -----------------------------------------------------
    # אין התאמות מפורשות וקיימות רק תוצאות ללא מידע גיל
    # -----------------------------------------------------

    if (
        match_count == 0
        and unknown_count > 0
    ):
        return (
            f"לא נמצאה התאמה שניתן לאשר לפי מידע גיל מפורש "
            f"לגיל {requested_age}. "
            f"קיימים {unknown_count} חוגים שעונים לשאר "
            f"תנאי החיפוש, אבל לא צוין עבורם טווח גיל במקור, "
            f"לכן אי אפשר לקבוע בוודאות אם הם מתאימים."
        )

    return None


# ---------------------------------------------------------
# בניית תשובה מוגבלת
# ---------------------------------------------------------

"""
בונה תשובה שמציגה מספר מוגבל של תוצאות
ומציינת כאשר קיימות תוצאות נוספות
"""
def _build_limited_answer(
    formatted_results: list[str],
    total_count: int,
    prefix: str | None = None,
) -> str:
    """
    בונה תשובה עם מספר מוגבל של תוצאות
    """

    visible_results = (
        formatted_results[
            :RESULT_LIMIT
        ]
    )

    answer_parts: list[str] = []

    if prefix:
        answer_parts.append(
            prefix
        )

    if total_count > RESULT_LIMIT:
        answer_parts.append(
            f"\nנמצאו {total_count} תוצאות בסך הכול. "
            f"מציג {RESULT_LIMIT} ראשונות:"
        )

    answer_parts.append(
        "\n".join(
            visible_results
        )
    )

    if total_count > RESULT_LIMIT:
        answer_parts.append(
            "\nרוצה לראות עוד?"
        )

    return "\n".join(
        answer_parts
    )


# ---------------------------------------------------------
# ביצוע חיפוש הפעילויות
# ---------------------------------------------------------

"""
מבצעת את חיפוש הפעילויות לפי התנאים שנשמרו
ומכינה את התשובה הסופית להצגה למשתמש
"""
def activity_node(
    state: AgentState,
) -> dict:

    results = search_activities(
        category=state.get(
            "category"
        ),
        age=state.get(
            "age"
        ),
        day=state.get(
            "day"
        ),
        start_after=state.get(
            "start_after"
        ),
        start_before=state.get(
            "start_before"
        ),
        location=state.get(
            "location"
        ),
        target_audience=state.get(
            "target_audience"
        ),
        center_name=state.get(
            "center_name"
        ),
        branch=state.get(
            "branch"
        ),
        instructor=state.get(
            "instructor"
        ),
    )

    # -----------------------------------------------------
    # אין תוצאות
    # -----------------------------------------------------

    if not results:

        requested_age = state.get(
            "age"
        )

        if requested_age is not None:
            no_results_answer = (
                f"לא נמצאו חוגים שעונים לתנאי החיפוש "
                f"עבור גיל {requested_age}."
            )

        else:
            no_results_answer = (
                "לא נמצאו חוגים מתאימים "
                "לפי תנאי החיפוש."
            )

        return {
            "tool_results": [],
            "waiting_for_clarification":
                False,
            "missing_information": [],
            "clarification_question":
                None,
            "final_answer":
                no_results_answer,
        }

    # -----------------------------------------------------
    # עיצוב התוצאות
    # -----------------------------------------------------

    formatted_results = [
        format_activity_hebrew(
            activity
        )
        for activity in results
    ]

    # -----------------------------------------------------
    # הסבר התאמת גיל
    # -----------------------------------------------------

    age_summary = (
        _activity_age_summary(
            state,
            results,
        )
    )

    # -----------------------------------------------------
    # בניית התשובה הסופית
    # -----------------------------------------------------

    final_answer = (
        _build_limited_answer(
            formatted_results=
                formatted_results,
            total_count=len(
                results
            ),
            prefix=age_summary,
        )
    )

    return {
        "tool_results":
            results,
        "waiting_for_clarification":
            False,
        "missing_information": [],
        "clarification_question":
            None,
        "final_answer":
            final_answer,
    }


# ---------------------------------------------------------
# בניית תרשים הזרימה
# ---------------------------------------------------------
#
# התחלה
#   │
#   ▼
# הכנת ההודעה לפי זיכרון השיחה
#   │
#   ▼
# ניתוח הבקשה
#   │
#   ├───────────────► חיפוש ─────────► סיום
#   │
#   ├───────────────► הבהרה ─────────► סיום
#   │
#   └───────────────► ניסיון הבנה נוסף
#                          │
#                          ├────────► חיפוש ───────► סיום
#                          │
#                          └────────► הבהרה ──────► סיום
#
# המצב הוא המידע המשותף שעובר בין שלבי העבודה
# ומתעדכן לאורך הזרימה
#
# המעברים מגדירים לאיזה שלב עוברים
# לאחר סיום כל שלב

"""
בונה את תרשים הזרימה של הסוכן
ומחברת בין זיכרון השיחה
שלבי ההבנה
החיפוש
ההבהרה
והניסיון הנוסף
"""
def build_graph():

    builder = StateGraph(
        AgentState
    )

    builder.add_node(
        "prepare_conversation_request",
        prepare_conversation_request,
    )

    builder.add_node(
        "understand_request",
        understand_request,
    )

    builder.add_node(
        "fallback_node",
        fallback_node,
    )

    builder.add_node(
        "activity_node",
        activity_node,
    )

    builder.add_node(
        "clarification_node",
        clarification_node,
    )

    builder.add_edge(
        START,
        "prepare_conversation_request",
    )

    builder.add_edge(
        "prepare_conversation_request",
        "understand_request",
    )

    builder.add_conditional_edges(
        "understand_request",
        route_after_understanding,
        {
            "activity_node":
                "activity_node",
            "fallback_node":
                "fallback_node",
            "clarification_node":
                "clarification_node",
        },
    )

    builder.add_conditional_edges(
        "fallback_node",
        route_after_fallback,
        {
            "activity_node":
                "activity_node",
            "clarification_node":
                "clarification_node",
        },
    )

    builder.add_edge(
        "activity_node",
        END,
    )

    builder.add_edge(
        "clarification_node",
        END,
    )

    return builder.compile(
        checkpointer=checkpointer
    )


graph = build_graph()


# ---------------------------------------------------------
# התאמת הצגת עברית במסוף
# ---------------------------------------------------------

"""
מגדירה קידוד מתאים להצגת טקסט בעברית במסוף
כאשר המערכת מופעלת בסביבת חלונות
"""
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
# בדיקות ידניות
# ---------------------------------------------------------

if __name__ == "__main__":

    _ensure_utf8_stdout()

    test_run_id = (
        uuid4().hex
    )

    test_questions = [

        # -------------------------------------------------
        # בקשות רגילות
        # -------------------------------------------------

        "מה יש היום?",
        "אילו חוגים יש במרכז הדס?",
        "אילו חוגים משה מעביר?",
        "אילו חוגים יש ביום שלישי אחרי 18:00?",

        # -------------------------------------------------
        # סוגי חוגים
        # -------------------------------------------------

        "פילאטיס",
        "יוגה",

        # -------------------------------------------------
        # שגיאות כתיב
        # -------------------------------------------------

        "אילו חוגים יש ביום שלשי?",
        "אילו חוגים יש במרקז הדס?",
        "איזה חוגים יש בשלשי ארב?",
        "מה יש ברבעי ארב?",
        "מה יש ברבעי בבקר?",

        # -------------------------------------------------
        # בקשות כלליות שדורשות הבהרה
        # -------------------------------------------------

        "אני רוצה משהו בערב",
        "אני רוצה משהו ביום רביעי",
        "אני מחפש משהו בבוקר",
        "אני מחפשת משהו מחר בערב",
        "בא לי משהו בערב",

        # -------------------------------------------------
        # בדיקת שגיאת כתיב עם משמעות
        # -------------------------------------------------

        "אני רוצה משהו ביום רבעי בבקר לגברים",

        # -------------------------------------------------
        # גיל
        # -------------------------------------------------

        "אילו חוגים מתאימים לגיל 16?",
        "אילו חוגים מתאימים לגיל 16 ביום שלישי?",
        "אילו חוגים מתאימים לגיל 16 ביום שלישי בערב?",
    ]

    for index, question in enumerate(
        test_questions,
        start=1,
    ):

        config = {
            "configurable": {
                "thread_id":
                    f"manual-test-{test_run_id}-{index}"
            }
        }

        result = graph.invoke(
            {
                "user_message":
                    question,
            },
            config,
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
            "Intent:",
            result.get(
                "intent"
            ),
        )

        print(
            "Confident:",
            result.get(
                "interpretation_confident"
            ),
        )

        print(
            "Fallback attempted:",
            result.get(
                "fallback_attempted"
            ),
        )

        print(
            "Age:",
            result.get(
                "age"
            ),
        )

        print(
            "Category:",
            result.get(
                "category"
            ),
        )

        print(
            "Target audience:",
            result.get(
                "target_audience"
            ),
        )

        print(
            "Day:",
            result.get(
                "day"
            ),
        )

        print(
            "Start after:",
            result.get(
                "start_after"
            ),
        )

        print(
            "Start before:",
            result.get(
                "start_before"
            ),
        )

        print(
            "Center:",
            result.get(
                "center_name"
            ),
        )

        print(
            "Waiting for clarification:",
            result.get(
                "waiting_for_clarification"
            ),
        )

        print(
            "Clarification question:",
            result.get(
                "clarification_question"
            ),
        )

        tool_results = result.get(
            "tool_results",
            [],
        )

        print(
            "מספר תוצאות:",
            len(
                tool_results
            ),
        )

        if result.get(
            "age"
        ) is not None:

            match_count = sum(
                1
                for activity in tool_results
                if activity.get(
                    "_age_match_status"
                ) == "match"
            )

            unknown_count = sum(
                1
                for activity in tool_results
                if activity.get(
                    "_age_match_status"
                ) == "unknown"
            )

            print(
                "התאמות גיל ודאיות:",
                match_count,
            )

            print(
                "ללא מידע גיל:",
                unknown_count,
            )

        print(
            "תשובה:"
        )

        print(
            result.get(
                "final_answer"
            )
        )

    # -----------------------------------------------------
    # בדיקות זיכרון שיחה
    # -----------------------------------------------------

    conversation_tests = [
        [
            "מה יש ביום שלישי?",
            "ומה בערב?",
        ],
        [
            "פילאטיס ביום שלישי בערב",
            "ומה בבוקר?",
        ],
        [
            "אני רוצה משהו בערב",
            "פילאטיס",
        ],
        [
            "מה יש ביום שלישי?",
            "אילו חוגים משה מעביר?",
        ],
    ]

    for conversation_index, messages in enumerate(
        conversation_tests,
        start=1,
    ):

        print(
            "\n"
            + "=" * 60
        )

        print(
            "בדיקת זיכרון:",
            conversation_index,
        )

        config = {
            "configurable": {
                "thread_id":
                    f"conversation-test-{test_run_id}-{conversation_index}"
            }
        }

        for message_index, user_message in enumerate(
            messages,
            start=1,
        ):

            result = graph.invoke(
                {
                    "user_message":
                        user_message,
                },
                config,
            )

            print(
                "\nהודעה:",
                message_index,
                user_message,
            )

            print(
                "פעולת שיחה:",
                result.get(
                    "conversation_action"
                ),
            )

            print(
                "יום:",
                result.get(
                    "day"
                ),
            )

            print(
                "סוג חוג:",
                result.get(
                    "category"
                ),
            )

            print(
                "התחלה:",
                result.get(
                    "start_after"
                ),
            )

            print(
                "סיום:",
                result.get(
                    "start_before"
                ),
            )

            print(
                "מדריך:",
                result.get(
                    "instructor"
                ),
            )

            print(
                "מחכה להבהרה:",
                result.get(
                    "waiting_for_clarification"
                ),
            )

            print(
                "תשובה:"
            )

            print(
                result.get(
                    "final_answer"
                )
            )
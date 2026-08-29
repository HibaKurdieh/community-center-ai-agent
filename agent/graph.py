from __future__ import annotations

import sys
from typing import Literal

from langgraph.graph import END, START, StateGraph

from request_parser import (
    parse_user_request,
    reinterpret_unclear_request,
)
from state import AgentState
from tools import (
    format_activity_hebrew,
    search_activities,
)


RESULT_LIMIT = 5


# ---------------------------------------------------------
# Node 1: Understand request using LLM
# ---------------------------------------------------------

def understand_request(
    state: AgentState,
) -> dict:
    """
    מנתח את בקשת המשתמש באמצעות ה-LLM.

    אם הבקשה ברורה:
    ממשיכים לחיפוש.

    אם הבקשה אינה ברורה:
    ה-Graph יעביר אותה לשלב fallback.
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
# Router after initial parsing
# ---------------------------------------------------------

def route_after_understanding(
    state: AgentState,
) -> Literal[
    "activity_node",
    "fallback_node",
    "clarification_node",
]:
    """
    מחליט האם אפשר כבר לחפש,
    האם צריך fallback,
    או האם כבר קיימת בקשת הבהרה.
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
# Fallback node
# ---------------------------------------------------------

def fallback_node(
    state: AgentState,
) -> dict:
    """
    ניסיון נוסף להבין בקשה לא ברורה.

    השלב מופעל רק כאשר הניתוח הראשון
    לא היה מספיק בטוח.

    מידע שכבר זוהה בשלב הראשון
    אינו נמחק אם ה-fallback לא החזיר
    ערך חדש עבור אותו שדה.
    """

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
# Router after fallback
# ---------------------------------------------------------

def route_after_fallback(
    state: AgentState,
) -> Literal[
    "activity_node",
    "clarification_node",
]:
    """
    אם ה-fallback הצליח להבין את הבקשה,
    ממשיכים לחיפוש.

    אחרת מבקשים הבהרה מהמשתמש.
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
# Clarification node
# ---------------------------------------------------------

def clarification_node(
    state: AgentState,
) -> dict:
    """
    מבקש הבהרה כאשר גם הניתוח הראשוני
    וגם ה-fallback לא הצליחו להבין מספיק.

    הניסוח ניטרלי מבחינת מגדר,
    וכל המידע שכבר זוהה נשמר ב-State.
    """

    known_parts: list[str] = []

    # -----------------------------------------------------
    # Day
    # -----------------------------------------------------

    day = state.get(
        "day"
    )

    if day:
        known_parts.append(
            f"ביום {day}"
        )

    # -----------------------------------------------------
    # Time
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
    # Center
    # -----------------------------------------------------

    center_name = state.get(
        "center_name"
    )

    if center_name:
        known_parts.append(
            f"במרכז {center_name}"
        )

    # -----------------------------------------------------
    # Branch
    # -----------------------------------------------------

    branch = state.get(
        "branch"
    )

    if branch:
        known_parts.append(
            f"בסניף {branch}"
        )

    # -----------------------------------------------------
    # Instructor
    # -----------------------------------------------------

    instructor = state.get(
        "instructor"
    )

    if instructor:
        known_parts.append(
            f"עם המדריך/ה {instructor}"
        )

    # -----------------------------------------------------
    # Location
    # -----------------------------------------------------

    location = state.get(
        "location"
    )

    if location:
        known_parts.append(
            f"במיקום {location}"
        )

    # -----------------------------------------------------
    # Audience
    # -----------------------------------------------------

    target_audience = state.get(
        "target_audience"
    )

    if target_audience:
        known_parts.append(
            f"לקהל {target_audience}"
        )

    # -----------------------------------------------------
    # Age
    # -----------------------------------------------------

    age = state.get(
        "age"
    )

    if age is not None:
        known_parts.append(
            f"לגיל {age}"
        )

    # -----------------------------------------------------
    # Build question
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
# Age-result helpers
# ---------------------------------------------------------

def _count_age_statuses(
    results: list[dict],
) -> tuple[int, int]:
    """
    סופר תוצאות לפי רמת ודאות גיל.

    מחזיר:
    (
        מספר התאמות גיל ודאיות,
        מספר תוצאות ללא מידע גיל
    )
    """

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


def _activity_age_summary(
    state: AgentState,
    results: list[dict],
) -> str | None:
    """
    בונה הסבר ברור כאשר המשתמש ציין גיל.

    חשוב להבדיל בין:

    match:
    יש מידע גיל במקור
    שמאשר התאמה.

    unknown:
    אין טווח גיל במקור,
    ולכן אי אפשר לאשר התאמה.

    תוצאות no_match כבר נפסלו
    בתוך search_activities.
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
    # All results have explicit matching age information
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
    # Some explicit matches + some unknown
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
    # No explicit matches, only unknown age
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
# Limited answer helper
# ---------------------------------------------------------

def _build_limited_answer(
    formatted_results: list[str],
    total_count: int,
    prefix: str | None = None,
) -> str:
    """
    בונה תשובה עם עד RESULT_LIMIT תוצאות.
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
# Activity node
# ---------------------------------------------------------

def activity_node(
    state: AgentState,
) -> dict:
    """
    מחפש חוגים בנתוני המרצה בלבד.

    כאשר צוין גיל:
    search_activities מחזיר קודם
    התאמות גיל ודאיות,
    ולאחר מכן תוצאות שבהן
    מידע הגיל אינו ידוע.
    """

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
    # No results
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
    # Format results
    # -----------------------------------------------------

    formatted_results = [
        format_activity_hebrew(
            activity
        )
        for activity in results
    ]

    # -----------------------------------------------------
    # Age explanation
    # -----------------------------------------------------

    age_summary = (
        _activity_age_summary(
            state,
            results,
        )
    )

    # -----------------------------------------------------
    # Build final answer
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
# Build graph

# LangGraph Flow
# ---------------------------------------------------------
#
# START
#   │
#   │  Edge רגיל
#   ▼
# understand_request
#   │
#   │  Conditional Edges
#   ├───────────────► activity_node ─────────► END
#   │
#   ├───────────────► clarification_node ────► END
#   │
#   └───────────────► fallback_node
#                          │
#                          │  Conditional Edges
#                          ├────────► activity_node ───────► END
#                          │
#                          └────────► clarification_node ─► END
#

# מצב: המידע המשותף שעובר בין שלבי העבודה ומתעדכן לאורך הזרימה.

# מעבר: החיבור שמגדיר לאיזה שלב עוברים אחרי שלב מסוים.

def build_graph():
    """
    בניית ה-LangGraph של סוכן החוגים.
    """

    builder = StateGraph(
        AgentState
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

    return builder.compile()


graph = build_graph()


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

    test_questions = [
        # -------------------------------------------------
        # Normal
        # -------------------------------------------------
        "מה יש היום?",
        "אילו חוגים יש במרכז הדס?",
        "אילו חוגים משה מעביר?",
        "אילו חוגים יש ביום שלישי אחרי 18:00?",

        # -------------------------------------------------
        # Category
        # -------------------------------------------------
        "פילאטיס",
        "יוגה",

        # -------------------------------------------------
        # Spelling errors
        # -------------------------------------------------
        "אילו חוגים יש ביום שלשי?",
        "אילו חוגים יש במרקז הדס?",
        "איזה חוגים יש בשלשי ארב?",
        "מה יש ברבעי ארב?",
        "מה יש ברבעי בבקר?",

        # -------------------------------------------------
        # Vague -> clarification
        # -------------------------------------------------
        "אני רוצה משהו בערב",
        "אני רוצה משהו ביום רביעי",
        "אני מחפש משהו בבוקר",
        "אני מחפשת משהו מחר בערב",
        "בא לי משהו בערב",

        # -------------------------------------------------
        # Important semantic typo test
        # -------------------------------------------------
        "אני רוצה משהו ביום רבעי בבקר לגברים",

        # -------------------------------------------------
        # Age
        # -------------------------------------------------
        "אילו חוגים מתאימים לגיל 16?",
        "אילו חוגים מתאימים לגיל 16 ביום שלישי?",
        "אילו חוגים מתאימים לגיל 16 ביום שלישי בערב?",
    ]

    for question in test_questions:

        result = graph.invoke(
            {
                "user_message":
                    question,
            }
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
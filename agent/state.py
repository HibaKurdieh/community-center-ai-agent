from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """
    המצב המשותף של סוכן החוגים.

    המידע ב-State עובר בין ה-Nodes השונים ב-LangGraph.
    בגרסה הנוכחית הסוכן עובד עם חוגים / פעילויות בלבד.
    """

    # -----------------------------------------------------
    # User input
    # -----------------------------------------------------

    user_message: str

    # activity / unknown
    intent: str

    # האם ה-LLM הבין את הבקשה בביטחון סביר
    interpretation_confident: bool

    # -----------------------------------------------------
    # Parsed request fields
    # -----------------------------------------------------

    age: int | None

    category: str | None

    target_audience: str | None

    day: str | None

    start_after: str | None

    start_before: str | None

    location: str | None

    # -----------------------------------------------------
    # Lecturer-data fields
    # -----------------------------------------------------

    center_name: str | None

    branch: str | None

    instructor: str | None

    # -----------------------------------------------------
    # Clarification / fallback state
    # -----------------------------------------------------

    # האם כבר בוצע ניסיון fallback
    fallback_attempted: bool

    # מידע שחסר או לא הובן
    missing_information: list[str]

    # שאלת הבהרה למשתמש
    clarification_question: str | None

    # האם הסוכן מחכה למידע נוסף
    waiting_for_clarification: bool

    # -----------------------------------------------------
    # Tool output
    # -----------------------------------------------------

    tool_results: list[
        dict[str, Any]
    ]

    # -----------------------------------------------------
    # Final response
    # -----------------------------------------------------

    final_answer: str
"""
POC: תשובות בעברית מתוך הנתונים בלבד (ללא מודל שפה חופשי).

הרצה מתיקיית הפרויקט:
  python agent/run_agent.py
  python agent/run_agent.py --interactive
"""

from __future__ import annotations

import sys


def _ensure_utf8_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stdin.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def _print_qa(question: str, answer_lines: list[str]) -> None:
    print("\n" + "—" * 48)
    print("שאלה:", question)
    print("תשובה (מתוך מסד הנתונים המקומי):")

    if not answer_lines:
        print("  לא נמצאו רשומות מתאימות בנתונים.")
        return

    for line in answer_lines:
        print(" ", line)


def run_demo() -> None:
    from tools import (
         format_activity_hebrew,
         reload_data,
         search_activities,
    )

    reload_data()

    # ---------------------------------------------------------
    # Test 1: Multiple filters - activities
    # ---------------------------------------------------------

    q1 = "אילו חוגי ספורט מתאימים לילד בן 9 ביום שלישי אחרי 16:00?"

    activities = search_activities(
        category="ספורט",
        age=9,
        day="שלישי",
        start_after="16:00",
    )

    _print_qa(
        q1,
        [format_activity_hebrew(activity) for activity in activities],
    )

    # ---------------------------------------------------------
    # Test 2: Age + day
    # ---------------------------------------------------------

    q2 = "אילו חוגים מתאימים לילד בן 10 ביום שלישי?"

    activities = search_activities(
        age=10,
        day="שלישי",
    )

    _print_qa(
        q2,
        [format_activity_hebrew(activity) for activity in activities],
    )
    

    # ---------------------------------------------------------
    # Test 5: Location filter
    # ---------------------------------------------------------

    q5 = "אילו חוגים מתקיימים באולם ספורט?"

    activities = search_activities(
        location="אולם ספורט",
    )

    _print_qa(
        q5,
        [format_activity_hebrew(activity) for activity in activities],
    )

    # ---------------------------------------------------------
    # Test 6: No results
    # ---------------------------------------------------------

    q6 = "אילו חוגים מתאימים לילד בן 1 ביום שלישי?"

    activities = search_activities(
        age=1,
        day="שלישי",
    )

    _print_qa(
        q6,
        [format_activity_hebrew(activity) for activity in activities],
    )


def _read_optional_int(prompt: str) -> int | None:
    value = input(prompt).strip()

    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        print("נא להזין מספר תקין.")
        return None
def run_interactive() -> None:
    from tools import (
        format_activity_hebrew,
        search_activities,
    )

    print(
        "\nברוכים הבאים למתנ\"ס הדיגיטלי"
    )

    print(
        "(חיפוש ישירות בנתוני הפעילויות — ללא LLM)\n"
    )

    category = (
        input(
            "קטגוריה (או Enter לדילוג): "
        ).strip()
        or None
    )

    age = _read_optional_int(
        "גיל המשתתף (או Enter לדילוג): "
    )

    day = (
        input(
            "יום (או Enter לדילוג): "
        ).strip()
        or None
    )

    start_after = (
        input(
            "משעת התחלה HH:MM (או Enter לדילוג): "
        ).strip()
        or None
    )

    start_before = (
        input(
            "עד שעת התחלה HH:MM (או Enter לדילוג): "
        ).strip()
        or None
    )

    location = (
        input(
            "מיקום (או Enter לדילוג): "
        ).strip()
        or None
    )

    results = search_activities(
        category=category,
        age=age,
        day=day,
        start_after=start_after,
        start_before=start_before,
        location=location,
    )

    print(
        "\n=== תוצאות חוגים ===\n"
    )

    if not results:
        print(
            "לא נמצאו חוגים מתאימים."
        )
        return

    for activity in results:
        print(
            "-",
            format_activity_hebrew(
                activity
            ),
        )



def main() -> None:
    _ensure_utf8_stdout()

    if "--interactive" in sys.argv:
        run_interactive()
    else:
        print(
            "הדגמת POC — חיפוש בעברית מתוך הקבצים המעובדים בלבד."
        )
        run_demo()


if __name__ == "__main__":
    main()

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
        format_event_hebrew,
        format_volunteer_hebrew,
        reload_data,
        search_activities,
        search_events,
        search_volunteer_opportunities,
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
    # Test 3: Events
    # ---------------------------------------------------------

    q3 = "אילו אירועים מיועדים לילדים?"

    events = search_events(
        target_age_group="ילדים",
    )

    _print_qa(
        q3,
        [format_event_hebrew(event) for event in events],
    )

    # ---------------------------------------------------------
    # Test 4: Volunteer opportunities
    # ---------------------------------------------------------

    q4 = "אילו הזדמנויות התנדבות מתאימות למתנדב בן 16?"

    opportunities = search_volunteer_opportunities(
        volunteer_age=16,
    )

    _print_qa(
        q4,
        [
            format_volunteer_hebrew(opportunity)
            for opportunity in opportunities
        ],
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
        format_event_hebrew,
        format_volunteer_hebrew,
        search_activities,
        search_events,
        search_volunteer_opportunities,
    )

    print("\nברוכים הבאים למתנ\"ס הדיגיטלי")
    print("(חיפוש ישירות בנתונים בלבד — ללא LLM)\n")

    print("בחר סוג חיפוש:")
    print("1 - חוגים")
    print("2 - אירועים")
    print("3 - התנדבות")

    choice = input("\nהכנס מספר: ").strip()

    # ---------------------------------------------------------
    # Activities
    # ---------------------------------------------------------

    if choice == "1":
        category = input("קטגוריה (או Enter לדילוג): ").strip() or None

        age = _read_optional_int(
            "גיל המשתתף (או Enter לדילוג): "
        )

        day = input(
            "יום (או Enter לדילוג): "
        ).strip() or None

        start_after = input(
            "משעת התחלה HH:MM (או Enter לדילוג): "
        ).strip() or None

        start_before = input(
            "עד שעת התחלה HH:MM (או Enter לדילוג): "
        ).strip() or None

        location = input(
            "מיקום (או Enter לדילוג): "
        ).strip() or None

        results = search_activities(
            category=category,
            age=age,
            day=day,
            start_after=start_after,
            start_before=start_before,
            location=location,
        )

        print("\n=== תוצאות חוגים ===\n")

        if not results:
            print("לא נמצאו חוגים מתאימים.")
            return

        for activity in results:
            print("-", format_activity_hebrew(activity))

    # ---------------------------------------------------------
    # Events
    # ---------------------------------------------------------

    elif choice == "2":
        target_age_group = input(
            "קהל יעד (או Enter לדילוג): "
        ).strip() or None

        day = input(
            "יום (או Enter לדילוג): "
        ).strip() or None

        location = input(
            "מיקום (או Enter לדילוג): "
        ).strip() or None

        start_after = input(
            "משעת התחלה HH:MM (או Enter לדילוג): "
        ).strip() or None

        start_before = input(
            "עד שעת התחלה HH:MM (או Enter לדילוג): "
        ).strip() or None

        results = search_events(
            target_age_group=target_age_group,
            day=day,
            location=location,
            start_after=start_after,
            start_before=start_before,
        )

        print("\n=== אירועים ===\n")

        if not results:
            print("לא נמצאו אירועים מתאימים.")
            return

        for event in results:
            print("-", format_event_hebrew(event))

    # ---------------------------------------------------------
    # Volunteering
    # ---------------------------------------------------------

    elif choice == "3":
        volunteer_age = _read_optional_int(
            "גיל המתנדב (או Enter לדילוג): "
        )

        day = input(
            "יום (או Enter לדילוג): "
        ).strip() or None

        location = input(
            "מיקום (או Enter לדילוג): "
        ).strip() or None

        start_after = input(
            "משעת התחלה HH:MM (או Enter לדילוג): "
        ).strip() or None

        start_before = input(
            "עד שעת התחלה HH:MM (או Enter לדילוג): "
        ).strip() or None

        results = search_volunteer_opportunities(
            volunteer_age=volunteer_age,
            day=day,
            location=location,
            start_after=start_after,
            start_before=start_before,
        )

        print("\n=== התנדבות ===\n")

        if not results:
            print("לא נמצאו אפשרויות התנדבות מתאימות.")
            return

        for opportunity in results:
            print("-", format_volunteer_hebrew(opportunity))

    else:
        print("בחירה לא חוקית.")


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

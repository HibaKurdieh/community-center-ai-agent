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
        print("  (אין רשומות מתאימות בנתונים.)")
    else:
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

    q1 = "אילו חוגי ספורט לילדים מתקיימים ביום שלישי אחרי 16:00?"
    acts = search_activities(
        category="ספורט",
        age_group="ילדים",
        day="שלישי",
        after_time="16:00:00",
    )
    _print_qa(q1, [format_activity_hebrew(a) for a in acts])

    q2 = "אילו אירועים מיועדים לילדים?"
    evs = search_events(target_age_group="ילדים")
    _print_qa(q2, [format_event_hebrew(e) for e in evs])

    q3 = "אילו הזדמנויות התנדבות מתאימות למתנדב בן 16?"
    vols = search_volunteer_opportunities(volunteer_age=16)
    _print_qa(q3, [format_volunteer_hebrew(v) for v in vols])


def run_interactive() -> None:
    from tools import (
        format_activity_hebrew,
        format_event_hebrew,
        format_volunteer_hebrew,
        search_activities,
        search_events,
        search_volunteer_opportunities,
    )

    print("\nברוכים הבאים למתנ\"ס הדיגיטלי (חיפוש בנתונים בלבד)\n")
    print("בחר סוג חיפוש:")
    print("1 - חוגים")
    print("2 - אירועים")
    print("3 - התנדבות")

    choice = input("\nהכנס מספר: ").strip()

    if choice == "1":
        category = input("קטגוריה (או ריק): ").strip() or None
        age_group = input("קבוצת גיל (או ריק): ").strip() or None
        day = input("יום (או ריק): ").strip() or None
        after = input("אחרי שעה HH:MM:SS (או ריק): ").strip() or None
        results = search_activities(
            category=category,
            age_group=age_group,
            day=day,
            after_time=after,
        )
        print("\n=== תוצאות ===\n")
        for a in results:
            print("-", format_activity_hebrew(a))
        if not results:
            print("לא נמצאו חוגים מתאימים.")

    elif choice == "2":
        target = input("קהל יעד (או ריק): ").strip() or None
        day = input("יום (או ריק): ").strip() or None
        results = search_events(target_age_group=target, day=day)
        print("\n=== אירועים ===\n")
        for e in results:
            print("-", format_event_hebrew(e))
        if not results:
            print("לא נמצאו אירועים.")

    elif choice == "3":
        age_s = input("גיל המתנדב (מספר): ").strip()
        volunteer_age = int(age_s) if age_s else None
        day = input("יום (או ריק): ").strip() or None
        results = search_volunteer_opportunities(volunteer_age=volunteer_age, day=day)
        print("\n=== התנדבות ===\n")
        for v in results:
            print("-", format_volunteer_hebrew(v))
        if not results:
            print("לא נמצאו אפשרויות התנדבות.")

    else:
        print("בחירה לא חוקית.")


def main() -> None:
    _ensure_utf8_stdout()
    if "--interactive" in sys.argv:
        run_interactive()
    else:
        print("הדגמת POC — שלוש שאלות בעברית, תשובות מתוך הקבצים המעובדים בלבד.")
        run_demo()


if __name__ == "__main__":
    main()

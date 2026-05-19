"""חיפוש בנתוני המתנ\"ס — כל התשובות מבוססות על קבצי JSON בלבד."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, time
from typing import Any

from paths import PROJECT_ROOT

_PROCESSED = PROJECT_ROOT / "data" / "processed"


def _load_json(name: str) -> list[dict[str, Any]]:
    path = _PROCESSED / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


activities: list[dict[str, Any]] = []
events: list[dict[str, Any]] = []
volunteer_opportunities: list[dict[str, Any]] = []


def reload_data() -> None:
    """טוען מחדש את ה-JSON (אחרי הרצת ingestion)."""
    global activities, events, volunteer_opportunities
    activities = _load_json("activities.json")
    events = _load_json("events.json")
    volunteer_opportunities = _load_json("volunteer_opportunities.json")


reload_data()


def _to_time(value: Any) -> time | None:
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                pass
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").time()
        except ValueError:
            pass
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            sec = int(m.group(3) or 0)
            return time(h, mi, sec)
    return None


def _time_gt(a: Any, b: Any) -> bool:
    """האם a > b (לשאילתות 'אחרי שעה X')."""
    ta, tb = _to_time(a), _to_time(b)
    if ta is None or tb is None:
        return False
    return (ta.hour, ta.minute, ta.second) > (tb.hour, tb.minute, tb.second)


def search_activities(
    category: str | None = None,
    age_group: str | None = None,
    day: str | None = None,
    after_time: str | None = None,
) -> list[dict[str, Any]]:
    """חוגים שבועיים — סינון לפי קטגוריה, קבוצת גיל, יום, ושעת התחלה (אחרי)."""
    results: list[dict[str, Any]] = []
    for activity in activities:
        if category and activity.get("category") != category:
            continue
        if age_group and activity.get("age_group") != age_group:
            continue
        if day and activity.get("day") != day:
            continue
        if after_time and not _time_gt(activity.get("start_time"), after_time):
            continue
        results.append(activity)
    return results


def search_events(
    target_age_group: str | None = None,
    day: str | None = None,
) -> list[dict[str, Any]]:
    """אירועים חד-פעמיים."""
    results: list[dict[str, Any]] = []
    for event in events:
        if target_age_group and event.get("target_age_group") != target_age_group:
            continue
        if day and event.get("day") != day:
            continue
        results.append(event)
    return results


def search_volunteer_opportunities(
    volunteer_age: int | None = None,
    day: str | None = None,
) -> list[dict[str, Any]]:
    """
    הזדמנויות התנדבות.

    volunteer_age: גיל המתנדב — יוצגו רק מקומות שבהם דרישת הגיל המינימלית
    של המתנ\"ס אינה גבוהה ממנו (כלומר המתנדב עומד בתנאי הגיל).
    """
    results: list[dict[str, Any]] = []
    for opportunity in volunteer_opportunities:
        req = opportunity.get("min_age")
        if volunteer_age is not None and req is not None and int(req) > volunteer_age:
            continue
        if day and opportunity.get("day") != day:
            continue
        results.append(opportunity)
    return results


def format_activity_hebrew(a: dict[str, Any]) -> str:
    return (
        f"{a.get('name', '')} — {a.get('day', '')} {a.get('start_time', '')}–{a.get('end_time', '')}, "
        f"גיל {a.get('min_age', '')}–{a.get('max_age', '')}, {a.get('instructor', '')}, "
        f"{a.get('location', '')}, מחיר {a.get('price', '')} ₪"
    )


def format_event_hebrew(e: dict[str, Any]) -> str:
    return (
        f"{e.get('name', '')} — {e.get('day', '')} {e.get('start_time', '')}, "
        f"קהל יעד: {e.get('target_age_group', '')}, מחיר {e.get('price', '')} ₪, {e.get('location', '')}"
    )


def format_volunteer_hebrew(v: dict[str, Any]) -> str:
    return (
        f"{v.get('title', '')} — {v.get('day', '')} {v.get('start_time', '')}, "
        f"גיל מינימלי למתנדב {v.get('min_age', '')}, {v.get('location', '')}, "
        f"איש קשר: {v.get('contact_person', '')}"
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    print("\n=== בדיקה: חוגי ספורט לילדים ביום שלישי אחרי 16:00 ===")
    for activity in search_activities(
        category="ספורט",
        age_group="ילדים",
        day="שלישי",
        after_time="16:00:00",
    ):
        print("-", format_activity_hebrew(activity))

"""
חיפוש בנתוני החוגים של מרכזי הספורט.

מקור הנתונים הפעיל של הסוכן:
- Supabase PostgreSQL database.

הפעילויות נטענות מ-Supabase
ומסוננות בצורה דטרמיניסטית לפי
יום, שעה, גיל, מרכז, מדריך ופרמטרים נוספים.

החיפוש מתבצע על נתוני הפעילויות הנטענים מ-Supabase.
לצורכי בדיקות, הערכה ומיגרציה בלבד,
אך אינם מקור הנתונים הפעיל של הסוכן.
"""

from __future__ import annotations
from pathlib import Path
import re
import sys
from datetime import datetime, time
from typing import Any
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.activities_repository import (
    get_all_activities,
)


synthetic_activities: list[
    dict[str, Any]
] = []

lecturer_activities: list[
    dict[str, Any]
] = []

activities: list[
    dict[str, Any]
] = []

def reload_data() -> None:
    """
     טוענת מחדש את נתוני הפעילויות ממסד הנתונים
     ומעדכנת את רשימת הפעילויות שבה משתמש הסוכן
    """

    global synthetic_activities
    global lecturer_activities
    global activities

    synthetic_activities = []

    lecturer_activities = (
        get_all_activities()
    )

    activities = (
        lecturer_activities
    )
reload_data()

def _to_time(
    value: Any,
) -> time | None:
    """
    ממירה ערכי זמן מסוגים שונים לפורמט זמן אחיד
    כדי לאפשר השוואה בין שעות
    """

    if value is None:
        return None

    if isinstance(
        value,
        time,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        text = value.strip()

        if not text:
            return None

        for fmt in (
            "%H:%M:%S",
            "%H:%M",
        ):
            try:
                return datetime.strptime(
                    text,
                    fmt,
                ).time()

            except ValueError:
                pass

        try:
            return datetime.strptime(
                text,
                "%Y-%m-%d %H:%M:%S",
            ).time()

        except ValueError:
            pass

        match = re.match(
            r"^(\d{1,2}):"
            r"(\d{2})"
            r"(?::(\d{2}))?",
            text,
        )

        if match:
            hour = int(
                match.group(1)
            )

            minute = int(
                match.group(2)
            )

            second = int(
                match.group(3)
                or 0
            )

            try:
                return time(
                    hour,
                    minute,
                    second,
                )

            except ValueError:
                return None

    return None


def _time_after(
    value: Any,
    threshold: Any,
) -> bool:
    """
    בודקת האם שעת הפעילות מאוחרת או שווה
    לשעת המינימום שהוגדרה בחיפוש
    """

    value_time = _to_time(
        value
    )

    threshold_time = _to_time(
        threshold
    )

    if (
        value_time is None
        or threshold_time is None
    ):
        return False

    return (
        value_time
        >= threshold_time
    )


def _time_before(
    value: Any,
    threshold: Any,
) -> bool:
    """
    בודקת האם שעת הפעילות מוקדמת או שווה
    לשעת המקסימום שהוגדרה בחיפוש
    """

    value_time = _to_time(
        value
    )

    threshold_time = _to_time(
        threshold
    )

    if (
        value_time is None
        or threshold_time is None
    ):
        return False

    return (
        value_time
        <= threshold_time
    )


# ---------------------------------------------------------
# Text helpers
# ---------------------------------------------------------

def _normalize_search_text(
    value: Any,
) -> str:
    """
    מנרמלת טקסט לצורך השוואה וחיפוש עקביים
    ומסירה רווחים מיותרים
    """

    if value is None:
        return ""

    text = str(
        value
    ).strip().casefold()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def _matches_text(
    value: Any,
    expected: str | None,
) -> bool:
    """
    מבצעת השוואת טקסט גמישה בין הערך מהנתונים
    לבין הערך שהמשתמש ביקש
    """

    if expected is None:
        return True

    if value is None:
        return False

    actual_text = (
        _normalize_search_text(
            value
        )
    )

    expected_text = (
        _normalize_search_text(
            expected
        )
    )

    if not expected_text:
        return True

    return (
        expected_text
        in actual_text
        or actual_text
        in expected_text
    )


# ---------------------------------------------------------
# Activity helpers
# ---------------------------------------------------------

def _activity_category(
    activity: dict[str, Any],
) -> str | None:
    """
    מחזירה את הקטגוריה של הפעילות
    ומשלימה קטגוריה כללית כאשר נדרש
    """

    category = activity.get(
        "category"
    )

    if category:
        return str(
            category
        )

    source_file = str(
        activity.get(
            "source_file",
            "",
        )
    )

    if source_file.endswith(
        ".docx"
    ):
        return "ספורט"

    return None


def _activity_type_matches(
    activity: dict[str, Any],
    requested: str | None,
) -> bool:
    """
    בודקת האם הפעילות מתאימה לסוג החוג המבוקש
    לפי קטגוריה שם הפעילות או השם באנגלית
    """

    if requested is None:
        return True

    general_category = (
        _activity_category(
            activity
        )
    )

    if _matches_text(
        general_category,
        requested,
    ):
        return True

    if _matches_text(
        activity.get(
            "name"
        ),
        requested,
    ):
        return True

    if _matches_text(
        activity.get(
            "english_name"
        ),
        requested,
    ):
        return True

    return False


# ---------------------------------------------------------
# Age helpers
# ---------------------------------------------------------

def _normalize_age_bound(
    value: Any,
) -> int | None:
    """
    מנרמלת ערכי גיל שמגיעים מהנתונים
    ומוודאת שמדובר בגיל מספרי ותקין
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        numeric_value = float(
            str(value).strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not numeric_value.is_integer():
        return None

    normalized = int(
        numeric_value
    )

    if normalized < 0:
        return None

    return normalized


def _age_match_status(
    activity: dict[str, Any],
    age: int,
) -> str:
    """
    בודקת את התאמת גיל המשתמש לטווח הגיל של הפעילות
    ומחזירה התאמה אי התאמה או מצב לא ידוע
    """

    min_age = (
        _normalize_age_bound(
            activity.get(
                "min_age"
            )
        )
    )

    max_age = (
        _normalize_age_bound(
            activity.get(
                "max_age"
            )
        )
    )

    if (
        min_age is None
        and max_age is None
    ):
        return "unknown"

    if (
        min_age is not None
        and age < min_age
    ):
        return "no_match"

    if (
        max_age is not None
        and age > max_age
    ):
        return "no_match"

    return "match"


def _age_match_priority(
    status: Any,
) -> int:
    """
    מגדירה את סדר העדיפות של תוצאות לפי ודאות הגיל
    כך שהתאמות מאושרות יופיעו לפני תוצאות לא ידועות
    """

    if status == "match":
        return 0

    if status == "unknown":
        return 1

    if status == "no_match":
        return 2

    return 3


def _sort_results_by_age_certainty(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    מסדרת את תוצאות החיפוש לפי רמת הוודאות של התאמת הגיל
    ומציגה התאמות מאושרות לפני מידע לא ידוע
    """

    return sorted(
        results,
        key=lambda activity:
            _age_match_priority(
                activity.get(
                    "_age_match_status"
                )
            ),
    )


# ---------------------------------------------------------
# Activity search
# ---------------------------------------------------------

def search_activities(
    category: str | None = None,
    age: int | None = None,
    day: str | None = None,
    start_after: str | None = None,
    start_before: str | None = None,
    location: str | None = None,
    target_audience: str | None = None,
    center_name: str | None = None,
    branch: str | None = None,
    instructor: str | None = None,
    include_cancelled: bool = False,
) -> list[dict[str, Any]]:
    """
    מחפשת פעילויות לפי תנאי החיפוש שהתקבלו מהסוכן
    ומסננת את הנתונים בצורה דטרמיניסטית לפי כל פילטר
    """

    results: list[
        dict[str, Any]
    ] = []

    for activity in activities:

        # -------------------------------------------------
        # Cancelled activities
        # -------------------------------------------------

        if (
            not include_cancelled
            and activity.get(
                "status"
            ) == "cancelled"
        ):
            continue

        # -------------------------------------------------
        # Category / activity type
        # -------------------------------------------------

        if not _activity_type_matches(
            activity,
            category,
        ):
            continue

        # -------------------------------------------------
        # Age
        # -------------------------------------------------

        age_match_status: str | None = None

        if age is not None:

            age_match_status = (
                _age_match_status(
                    activity,
                    age,
                )
            )

            if (
                age_match_status
                == "no_match"
            ):
                continue

        # -------------------------------------------------
        # Day
        # -------------------------------------------------

        if (
            day
            and not _matches_text(
                activity.get(
                    "day"
                ),
                day,
            )
        ):
            continue

        # -------------------------------------------------
        # Time
        # -------------------------------------------------

        if (
            start_after
            and not _time_after(
                activity.get(
                    "start_time"
                ),
                start_after,
            )
        ):
            continue

        if (
            start_before
            and not _time_before(
                activity.get(
                    "start_time"
                ),
                start_before,
            )
        ):
            continue

        # -------------------------------------------------
        # Location
        # -------------------------------------------------

        if (
            location
            and not _matches_text(
                activity.get(
                    "location"
                ),
                location,
            )
        ):
            continue

        # -------------------------------------------------
        # Target audience
        # -------------------------------------------------

        if (
            target_audience
            and not _matches_text(
                activity.get(
                    "target_audience"
                ),
                target_audience,
            )
        ):
            continue

        # -------------------------------------------------
        # Center
        # -------------------------------------------------

        if (
            center_name
            and not _matches_text(
                activity.get(
                    "center_name"
                ),
                center_name,
            )
        ):
            continue

        # -------------------------------------------------
        # Branch
        # -------------------------------------------------

        if (
            branch
            and not _matches_text(
                activity.get(
                    "branch"
                ),
                branch,
            )
        ):
            continue

        # -------------------------------------------------
        # Instructor
        # -------------------------------------------------

        if (
            instructor
            and not _matches_text(
                activity.get(
                    "instructor"
                ),
                instructor,
            )
        ):
            continue

        # -------------------------------------------------
        # Safe copy for response metadata
        # -------------------------------------------------

        result_activity = dict(
            activity
        )

        if age is not None:

            result_activity[
                "_requested_age"
            ] = age

            result_activity[
                "_age_match_status"
            ] = age_match_status

        results.append(
            result_activity
        )

    # -----------------------------------------------------
    # Age-aware ranking
    # -----------------------------------------------------

    if age is not None:

        results = (
            _sort_results_by_age_certainty(
                results
            )
        )

    return results


# ---------------------------------------------------------
# Hebrew formatting
# ---------------------------------------------------------

def _display_value(
    value: Any,
) -> str:
    """
    ממירה ערך לצורה בטוחה להצגה
    ומחזירה טקסט ריק כאשר אין ערך
    """

    if value is None:
        return ""

    return str(
        value
    )


def format_activity_hebrew(
    activity: dict[str, Any],
) -> str:
    """
    מעצבת את פרטי הפעילות לטקסט ברור בעברית
    ומציגה את כל המידע הזמין בצורה קריאה
    """

    parts: list[str] = []

    name = _display_value(
        activity.get(
            "name"
        )
    )

    day = _display_value(
        activity.get(
            "day"
        )
    )

    start_time = _display_value(
        activity.get(
            "start_time"
        )
    )

    end_time = _display_value(
        activity.get(
            "end_time"
        )
    )

    # -----------------------------------------------------
    # Basic class information
    # -----------------------------------------------------

    if end_time:
        parts.append(
            f"{name} — "
            f"{day} "
            f"{start_time}–{end_time}"
        )

    else:
        parts.append(
            f"{name} — "
            f"{day} "
            f"{start_time}"
        )

    # -----------------------------------------------------
    # Center
    # -----------------------------------------------------

    center_name = activity.get(
        "center_name"
    )

    if center_name:
        parts.append(
            f"מרכז: {center_name}"
        )

    # -----------------------------------------------------
    # Branch
    # -----------------------------------------------------

    branch = activity.get(
        "branch"
    )

    if branch:
        parts.append(
            f"סניף {branch}"
        )

    # -----------------------------------------------------
    # Instructor
    # -----------------------------------------------------

    instructor = activity.get(
        "instructor"
    )

    if instructor:
        parts.append(
            f"מדריך/ה: {instructor}"
        )

    # -----------------------------------------------------
    # Location
    # -----------------------------------------------------

    location = activity.get(
        "location"
    )

    if location:
        parts.append(
            f"מיקום: {location}"
        )

    # -----------------------------------------------------
    # Age
    # -----------------------------------------------------

    min_age = (
        _normalize_age_bound(
            activity.get(
                "min_age"
            )
        )
    )

    max_age = (
        _normalize_age_bound(
            activity.get(
                "max_age"
            )
        )
    )

    if (
        min_age is not None
        and max_age is not None
    ):
        parts.append(
            f"גיל {min_age}–{max_age}"
        )

    elif min_age is not None:
        parts.append(
            f"מגיל {min_age}"
        )

    elif max_age is not None:
        parts.append(
            f"עד גיל {max_age}"
        )

    age_match_status = activity.get(
        "_age_match_status"
    )

    if (
        age_match_status
        == "unknown"
    ):
        parts.append(
            "לא צוין טווח גיל במקור"
        )

    # -----------------------------------------------------
    # Audience
    # -----------------------------------------------------

    target_audience = activity.get(
        "target_audience"
    )

    if target_audience:
        parts.append(
            f"קהל: {target_audience}"
        )

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    status = activity.get(
        "status"
    )

    if (
        status
        and status != "active"
    ):
        parts.append(
            f"סטטוס: {status}"
        )

    # -----------------------------------------------------
    # Notes
    # -----------------------------------------------------

    notes = activity.get(
        "notes"
    )

    if notes:
        parts.append(
            f"הערות: {notes}"
        )

    return ", ".join(
        parts
    )


# ---------------------------------------------------------
# Manual tests
# ---------------------------------------------------------

if __name__ == "__main__":

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

    reload_data()

    print(
        "\n=== Data Sources ==="
    )

    print(
        "Synthetic activities "
        "(testing/evaluation only):",
        len(
            synthetic_activities
        ),
    )

    print(
        "Lecturer activities:",
        len(
            lecturer_activities
        ),
    )

    print(
        "Activities used by agent:",
        len(
            activities
        ),
    )

    # -----------------------------------------------------
    # Test 1
    # -----------------------------------------------------

    print(
        "\n=== בדיקה 1: "
        "חוגים ביום שלישי ==="
    )

    results = search_activities(
        day="שלישי",
    )

    print(
        "נמצאו:",
        len(results),
    )

    for activity in results[:10]:
        print(
            "-",
            format_activity_hebrew(
                activity
            ),
        )

    # -----------------------------------------------------
    # Test 2
    # -----------------------------------------------------

    print(
        "\n=== בדיקה 2: "
        "חוגים ביום שלישי אחרי 18:00 ==="
    )

    results = search_activities(
        day="שלישי",
        start_after="18:00",
    )

    print(
        "נמצאו:",
        len(results),
    )

    for activity in results[:10]:
        print(
            "-",
            format_activity_hebrew(
                activity
            ),
        )

    # -----------------------------------------------------
    # Test 3
    # -----------------------------------------------------

    print(
        "\n=== בדיקה 3: "
        "חוגים במרכז הדס ==="
    )

    results = search_activities(
        center_name="הדס",
    )

    print(
        "נמצאו:",
        len(results),
    )

    for activity in results[:10]:
        print(
            "-",
            format_activity_hebrew(
                activity
            ),
        )

    # -----------------------------------------------------
    # Test 4
    # -----------------------------------------------------

    print(
        "\n=== בדיקה 4: "
        "חוגי פילאטיס ==="
    )

    results = search_activities(
        category="פילאטיס",
    )

    print(
        "נמצאו:",
        len(results),
    )

    for activity in results[:10]:
        print(
            "-",
            format_activity_hebrew(
                activity
            ),
        )

    # -----------------------------------------------------
    # Test 5
    # -----------------------------------------------------

    print(
        "\n=== בדיקה 5: "
        "חוגים לגיל 9 ביום שלישי ==="
    )

    results = search_activities(
        age=9,
        day="שלישי",
    )

    print(
        "נמצאו:",
        len(results),
    )

    print(
        "התאמות גיל ודאיות:",
        sum(
            1
            for activity in results
            if activity.get(
                "_age_match_status"
            ) == "match"
        ),
    )

    print(
        "גיל לא ידוע במקור:",
        sum(
            1
            for activity in results
            if activity.get(
                "_age_match_status"
            ) == "unknown"
        ),
    )

    for activity in results[:10]:
        print(
            "-",
            activity.get(
                "_age_match_status"
            ),
            "|",
            format_activity_hebrew(
                activity
            ),
        )

    # -----------------------------------------------------
    # Test 6
    # -----------------------------------------------------

    print(
        "\n=== בדיקה 6: "
        "חוגים לגיל 16 ==="
    )

    results = search_activities(
        age=16,
    )

    print(
        "נמצאו:",
        len(results),
    )

    print(
        "התאמות גיל ודאיות:",
        sum(
            1
            for activity in results
            if activity.get(
                "_age_match_status"
            ) == "match"
        ),
    )

    print(
        "גיל לא ידוע במקור:",
        sum(
            1
            for activity in results
            if activity.get(
                "_age_match_status"
            ) == "unknown"
        ),
    )

    for activity in results[:10]:
        print(
            "-",
            activity.get(
                "_age_match_status"
            ),
            "|",
            format_activity_hebrew(
                activity
            ),
        )

    # -----------------------------------------------------
    # Test 7
    # -----------------------------------------------------

    print(
        "\n=== בדיקה 7: "
        "גיל 16 ביום שלישי בערב ==="
    )

    results = search_activities(
        age=16,
        day="שלישי",
        start_after="17:00",
        start_before="23:59",
    )

    print(
        "נמצאו:",
        len(results),
    )

    for activity in results:
        print(
            "-",
            activity.get(
                "_age_match_status"
            ),
            "|",
            format_activity_hebrew(
                activity
            ),
        )
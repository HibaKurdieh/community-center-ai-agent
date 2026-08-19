"""
חיפוש בנתוני החוגים של מרכזי הספורט.

מקור הנתונים הפעיל של הסוכן:
- רק הפעילויות שחולצו ממסמכי המרצה.

הדאטה הסינטטי של החוגים נשמר בפרויקט
לצורכי בדיקות והערכה בלבד,
אך אינו משתתף בחיפוש של הסוכן.

כל החיפוש מתבצע על קובצי JSON מעובדים בלבד.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, time
from typing import Any

from paths import PROJECT_ROOT


_PROCESSED = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


# ---------------------------------------------------------
# JSON loading
# ---------------------------------------------------------

def _load_json(
    name: str,
    required: bool = True,
) -> list[dict[str, Any]]:
    """
    טוען קובץ JSON מתוך data/processed.

    required=False מאפשר לעבוד גם אם
    קובץ אופציונלי עדיין לא קיים.
    """

    path = (
        _PROCESSED
        / name
    )

    if not path.exists():

        if required:
            raise FileNotFoundError(
                f"לא נמצא קובץ: {path}"
            )

        return []

    with open(
        path,
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    if not isinstance(
        data,
        list,
    ):
        raise ValueError(
            f"הקובץ {name} חייב להכיל רשימת רשומות."
        )

    return data


# ---------------------------------------------------------
# In-memory data
# ---------------------------------------------------------

# נשמר רק לצורכי testing / evaluation.
synthetic_activities: list[
    dict[str, Any]
] = []


# הפעילויות שחולצו מקבצי המרצה.
lecturer_activities: list[
    dict[str, Any]
] = []


# זהו מקור הנתונים שבו הסוכן משתמש בפועל.
activities: list[
    dict[str, Any]
] = []


def reload_data() -> None:
    """
    טוען מחדש את קובצי הפעילויות.

    חשוב:
    - synthetic_activities נשמר רק לבדיקה.
    - lecturer_activities הוא מקור הנתונים האמיתי.
    - activities מכיל רק את נתוני המרצה.
    """

    global synthetic_activities
    global lecturer_activities
    global activities

    synthetic_activities = _load_json(
        "activities.json",
        required=False,
    )

    lecturer_activities = _load_json(
        "activities_from_lecturer.json",
        required=True,
    )

    activities = (
        lecturer_activities
    )


reload_data()


# ---------------------------------------------------------
# Time helpers
# ---------------------------------------------------------

def _to_time(
    value: Any,
) -> time | None:
    """
    ממיר ערך זמן ל-time
    כדי לאפשר השוואות.
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
    בודק האם value מאוחר או שווה
    ל-threshold.
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
    בודק האם value מוקדם או שווה
    ל-threshold.
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
    מנרמל טקסט לצורך חיפוש גמיש.
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
    השוואת טקסט גמישה.

    לדוגמה:
    "אולם" מתאים גם ל-"אולם ספורט".
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
    מחזיר קטגוריית פעילות כללית.

    קבצי המרצה מתארים מרכזי ספורט,
    ולכן פעילות ללא category מפורש
    מסווגת לצורכי החיפוש כ-"ספורט".
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
    בודק התאמה לסוג החוג המבוקש.

    מאפשר גם:
    category="ספורט"

    וגם בקשות כמו:
    category="פילאטיס"
    category="יוגה"

    כלומר מחפשים גם בקטגוריה הכללית
    וגם בשם החוג.
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
    מנרמל ערך גיל שמגיע מהדאטה.

    תומך למשל ב:
    16
    16.0
    "16"
    "16.0"

    אם הערך אינו מספר תקין,
    מוחזר None.
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
    מחזיר סטטוס התאמת גיל.

    אפשרויות:

    match:
    קיים מידע גיל מפורש
    והגיל המבוקש מתאים.

    no_match:
    קיים מידע גיל מפורש
    והגיל המבוקש אינו מתאים.

    unknown:
    אין מספיק מידע גיל במקור.

    חשוב:
    unknown אינו מוצג כהתאמה ודאית,
    אך גם אינו נפסל אוטומטית.
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
    קובע סדר עדיפות בתוצאות גיל.

    match:
    מידע מפורש שמאשר התאמה.

    unknown:
    אין מספיק מידע במקור.

    no_match:
    אמור להיפסל לפני שלב המיון,
    אך נשמרת עדיפות גם לצורכי בטיחות.
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
    מסדר תוצאות לפי רמת הוודאות
    של התאמת הגיל.

    ההתאמות המאושרות מופיעות ראשונות,
    ולאחריהן פעילויות שאין לגביהן
    מידע גיל במקור.

    sort של Python הוא stable,
    ולכן הסדר המקורי נשמר
    בתוך כל קבוצת ודאות.
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
    חיפוש חוגים בנתוני המרצה בלבד.

    ניתן לסנן לפי:
    - סוג חוג / category
    - גיל
    - יום
    - שעה
    - מיקום
    - קהל יעד
    - מרכז
    - סניף
    - מדריך

    כאשר המשתמש מציין גיל:

    1. אם קיים טווח גיל מפורש
       והמשתמש אינו מתאים:
       הפעילות נפסלת.

    2. אם קיים טווח גיל מפורש
       והמשתמש מתאים:
       הפעילות מסומנת match.

    3. אם אין מידע גיל במקור:
       הפעילות נשארת אך מסומנת unknown.

    4. תוצאות match מוצגות לפני unknown.

    כך המערכת אינה ממציאה התאמת גיל,
    אך גם אינה מסתירה פעילויות
    שאין לגביהן מידע מספיק.
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
    מחזיר ערך להצגה בטוחה.
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
    מציג פעילות בצורה קריאה בעברית.

    אם המשתמש ביקש התאמה לפי גיל
    אך אין טווח גיל במקור,
    הדבר מצוין במפורש.
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
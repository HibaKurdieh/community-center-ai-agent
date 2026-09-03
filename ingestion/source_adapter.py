"""
הקובץ מתאים רשומות שמגיעות ממקורות נתונים מובנים
כמו קובצי גיליון או מקור נתונים חיצוני
למבנה הפעילות האחיד של המערכת

כך כל מקור חדש צריך רק שכבת קריאה או שכבת התאמה מתאימה
בעוד ששאר תהליך קליטת הנתונים נשאר ללא שינוי
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from typing import Any

from ingestion.normalize import (
    normalize_day,
    normalize_status,
    normalize_text,
    normalize_time,
)
from ingestion.time_inference import (
    infer_end_time,
)


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "center_name": (
        "center_name",
        "center",
        "community_center",
        "sport_center",
        "מרכז",
        "שם מרכז",
        "שם המרכז",
    ),
    "branch": (
        "branch",
        "branch_name",
        "סניף",
    ),
    "day": (
        "day",
        "weekday",
        "יום",
    ),
    "start_time": (
        "start_time",
        "start",
        "time",
        "שעת התחלה",
        "שעה",
    ),
    "end_time": (
        "end_time",
        "end",
        "שעת סיום",
    ),
    "duration_minutes": (
        "duration_minutes",
        "duration",
        "משך",
        "משך בדקות",
    ),
    "name": (
        "name",
        "activity_name",
        "activity",
        "title",
        "שם",
        "שם פעילות",
        "שם החוג",
        "חוג",
    ),
    "english_name": (
        "english_name",
        "name_en",
        "english title",
    ),
    "instructor": (
        "instructor",
        "teacher",
        "trainer",
        "מדריך",
        "מדריכה",
    ),
    "location": (
        "location",
        "room",
        "place",
        "מיקום",
        "חדר",
    ),
    "target_audience": (
        "target_audience",
        "audience",
        "age_group",
        "קהל יעד",
        "קהל",
        "קבוצת גיל",
    ),
    "min_age": (
        "min_age",
        "minimum_age",
        "גיל מינימלי",
    ),
    "max_age": (
        "max_age",
        "maximum_age",
        "גיל מקסימלי",
    ),
    "capacity": (
        "capacity",
        "max_participants",
        "קיבולת",
    ),
    "level": (
        "level",
        "רמה",
    ),
    "notes": (
        "notes",
        "description",
        "הערות",
        "תיאור",
    ),
    "season": (
        "season",
        "עונה",
    ),
    "valid_from": (
        "valid_from",
        "start_date",
        "תאריך התחלה",
    ),
    "source_language": (
        "source_language",
        "language",
        "שפה",
    ),
    "status": (
        "status",
        "state",
        "סטטוס",
        "מצב",
    ),
}


def _normalize_key(
    value: Any,
) -> str:
    """
    מנרמלת שם של שדה
    כדי לאפשר התאמה בין שמות עמודות ממקורות שונים
    """

    text = str(
        value
    ).strip().casefold()

    text = re.sub(
        r"[\s\-]+",
        "_",
        text,
    )

    return text


def _is_missing(
    value: Any,
) -> bool:
    """
    בודקת אם הערך חסר או ריק
    כולל ערכים מספריים חסרים שיכולים להגיע מקובצי גיליון
    """

    if value is None:
        return True

    if (
        isinstance(
            value,
            float,
        )
        and math.isnan(
            value
        )
    ):
        return True

    return False


def _stringify(
    value: Any,
) -> str | None:
    """
    ממירה ערכים מסוגים שונים
    למחרוזת אחידה שניתן להמשיך לעבד
    """

    if _is_missing(
        value
    ):
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat(
            sep=" "
        )

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    if isinstance(
        value,
        time,
    ):
        return value.strftime(
            "%H:%M"
        )

    text = str(
        value
    ).strip()

    return text or None


def _as_int(
    value: Any,
) -> int | None:
    """
    ממירה ערך מספרי למספר שלם
    כאשר ניתן לבצע את ההמרה בצורה בטוחה
    """

    if _is_missing(
        value
    ):
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        numeric = float(
            str(value).strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not numeric.is_integer():
        return None

    return int(
        numeric
    )


def _prepare_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    מנרמלת את שמות השדות של רשומת המקור
    לפני ניסיון ההתאמה למבנה האחיד
    """

    return {
        _normalize_key(key): value
        for key, value in record.items()
    }


def _get_value(
    record: dict[str, Any],
    field_name: str,
) -> Any:
    """
    מחפשת ערך ברשומה
    לפי שמות השדות החלופיים המוכרים למערכת
    """

    aliases = FIELD_ALIASES.get(
        field_name,
        (field_name,),
    )

    for alias in aliases:

        normalized_alias = (
            _normalize_key(
                alias
            )
        )

        if normalized_alias in record:

            value = record[
                normalized_alias
            ]

            if not _is_missing(
                value
            ):
                return value

    return None


def _detect_language(
    *values: str | None,
) -> str:
    """
    מזהה אם המידע במקור הוא בעברית
    באנגלית או משלב בין שתי השפות
    """

    text = " ".join(
        value
        for value in values
        if value
    )

    has_hebrew = bool(
        re.search(
            r"[\u0590-\u05FF]",
            text,
        )
    )

    has_english = bool(
        re.search(
            r"[A-Za-z]",
            text,
        )
    )

    if (
        has_hebrew
        and has_english
    ):
        return "mixed"

    if has_english:
        return "en"

    return "he"


def adapt_activity_record(
    record: dict[str, Any],
    *,
    source_name: str,
    default_center_name: str | None = None,
) -> dict[str, Any]:
    """
    ממירה רשומה שמגיעה מקובץ גיליון או ממקור חיצוני
    למבנה הפעילות האחיד שבו משתמשת המערכת
    """

    prepared = _prepare_record(
        record
    )

    raw_day = _stringify(
        _get_value(
            prepared,
            "day",
        )
    )

    raw_name = _stringify(
        _get_value(
            prepared,
            "name",
        )
    )

    raw_start_time = _stringify(
        _get_value(
            prepared,
            "start_time",
        )
    )

    raw_end_time = _stringify(
        _get_value(
            prepared,
            "end_time",
        )
    )

    start_time = normalize_time(
        raw_start_time
    )

    explicit_end_time = normalize_time(
        raw_end_time
    )

    duration_minutes = _as_int(
        _get_value(
            prepared,
            "duration_minutes",
        )
    )

    end_time, end_time_source = (
        infer_end_time(
            source_file=source_name,
            activity_name=raw_name or "",
            start_time=start_time,
            day=raw_day,
            explicit_end_time=explicit_end_time,
            duration_minutes=duration_minutes,
        )
    )

    center_name = normalize_text(
        _stringify(
            _get_value(
                prepared,
                "center_name",
            )
        )
    )

    if (
        center_name is None
        and default_center_name
    ):
        center_name = normalize_text(
            default_center_name
        )

    target_audience = normalize_text(
        _stringify(
            _get_value(
                prepared,
                "target_audience",
            )
        )
    )

    explicit_language = _stringify(
        _get_value(
            prepared,
            "source_language",
        )
    )

    if explicit_language in {
        "he",
        "en",
        "mixed",
        "bilingual",
    }:
        source_language = (
            explicit_language
        )

    else:
        source_language = (
            _detect_language(
                raw_name,
                raw_day,
                center_name,
            )
        )

    raw_status = _stringify(
        _get_value(
            prepared,
            "status",
        )
    )

    return {
        "source_file": source_name,
        "center_name": center_name,
        "branch": normalize_text(
            _stringify(
                _get_value(
                    prepared,
                    "branch",
                )
            )
        ),
        "day": normalize_day(
            raw_day
        ),
        "raw_day": raw_day,
        "start_time": start_time,
        "end_time": end_time,
        "end_time_source": (
            end_time_source
        ),
        "raw_time": (
            raw_start_time
            if raw_end_time is None
            else (
                f"{raw_start_time or ''}"
                f"-{raw_end_time}"
            )
        ),
        "name": normalize_text(
            raw_name
        ),
        "raw_name": raw_name,
        "english_name": normalize_text(
            _stringify(
                _get_value(
                    prepared,
                    "english_name",
                )
            )
        ),
        "instructor": normalize_text(
            _stringify(
                _get_value(
                    prepared,
                    "instructor",
                )
            )
        ),
        "location": normalize_text(
            _stringify(
                _get_value(
                    prepared,
                    "location",
                )
            )
        ),
        "target_audience": (
            target_audience
        ),
        "min_age": _as_int(
            _get_value(
                prepared,
                "min_age",
            )
        ),
        "max_age": _as_int(
            _get_value(
                prepared,
                "max_age",
            )
        ),
        "capacity": _as_int(
            _get_value(
                prepared,
                "capacity",
            )
        ),
        "level": normalize_text(
            _stringify(
                _get_value(
                    prepared,
                    "level",
                )
            )
        ),
        "notes": normalize_text(
            _stringify(
                _get_value(
                    prepared,
                    "notes",
                )
            )
        ),
        "season": normalize_text(
            _stringify(
                _get_value(
                    prepared,
                    "season",
                )
            )
        ),
        "valid_from": _stringify(
            _get_value(
                prepared,
                "valid_from",
            )
        ),
        "source_language": (
            source_language
        ),
        "status": normalize_status(
            raw_status
        ),
    }
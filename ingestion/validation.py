"""
הקובץ אחראי לבדוק את תקינות הפעילויות לאחר שלב הפענוח

הוא בודק שדות חובה ערכים חוקיים שעות גילאים קיבולת וכפילויות
ומבדיל בין שגיאות קריטיות לבין אזהרות

המטרה היא לוודא שרק נתונים תקינים ואמינים ימשיכו לשלב הבא
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


VALID_DAYS = {
    "ראשון",
    "שני",
    "שלישי",
    "רביעי",
    "חמישי",
    "שישי",
    "שבת",
}


VALID_STATUSES = {
    "active",
    "cancelled",
    "tbd",
}


VALID_SOURCE_LANGUAGES = {
    "he",
    "en",
    "mixed",
    "bilingual",
}


VALID_END_TIME_SOURCES = {
    "explicit",
    "inferred_source_rule",
    "missing",
}


REQUIRED_FIELDS = (
    "source_file",
    "center_name",
    "day",
    "raw_day",
    "start_time",
    "name",
    "raw_name",
    "target_audience",
    "source_language",
    "status",
)


TIME_PATTERN = re.compile(
    r"^\d{2}:\d{2}$"
)


# ---------------------------------------------------------
# Validation result models
# ---------------------------------------------------------


@dataclass
class ActivityValidation:
    """
    תוצאת הבדיקה של פעילות אחת.
    """

    index: int

    critical_errors: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    @property
    def is_valid(self) -> bool:
        """
        פעילות נחשבת תקינה
        כאשר אין שגיאות קריטיות.
        """

        return not self.critical_errors


@dataclass
class ValidationReport:
    """
    דוח מסכם עבור רשימת פעילויות.
    """

    total_records: int
    valid_records: int
    invalid_records: int
    duplicate_count: int

    critical_errors: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    records: list[
        ActivityValidation
    ] = field(
        default_factory=list
    )

    @property
    def passed(self) -> bool:
        """
        התוצאה עוברת רק אם קיימת
        לפחות פעילות אחת
        ואין רשומות עם שגיאות קריטיות.
        """

        return (
            self.total_records > 0
            and self.invalid_records == 0
        )

    @property
    def valid_ratio(self) -> float:
        """
        אחוז הרשומות התקינות.
        """

        if self.total_records == 0:
            return 0.0

        return (
            self.valid_records
            / self.total_records
        )


# ---------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------


def _has_value(
    value: Any,
) -> bool:
    """
    בודק אם קיים ערך שימושי.
    """

    if value is None:
        return False

    if isinstance(
        value,
        str,
    ):
        return bool(
            value.strip()
        )

    return True


def _parse_time(
    value: Any,
) -> datetime | None:
    """
    בודק ששעה נמצאת
    בפורמט HH:MM
    וגם מייצגת שעה חוקית.
    """

    if not isinstance(
        value,
        str,
    ):
        return None

    if not TIME_PATTERN.fullmatch(
        value
    ):
        return None

    try:
        return datetime.strptime(
            value,
            "%H:%M",
        )

    except ValueError:
        return None


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    יוצר מפתח לצורך זיהוי כפילויות.
    """

    return (
        activity.get(
            "center_name"
        ),
        activity.get(
            "branch"
        ),
        activity.get(
            "day"
        ),
        activity.get(
            "start_time"
        ),
        activity.get(
            "end_time"
        ),
        activity.get(
            "name"
        ),
        activity.get(
            "instructor"
        ),
        activity.get(
            "location"
        ),
    )


# ---------------------------------------------------------
# Single activity validation
# ---------------------------------------------------------


def validate_activity(
    activity: Any,
    *,
    index: int = 0,
) -> ActivityValidation:
    """
    מבצע Validation לפעילות אחת.

    שגיאה קריטית:
    מידע שלא ניתן לשמור בבטחה.

    Warning:
    מידע חשוד או חסר,
    אך לא בהכרח שגוי.
    """

    result = ActivityValidation(
        index=index
    )

    # -----------------------------------------------------
    # Basic structure
    # -----------------------------------------------------

    if not isinstance(
        activity,
        dict,
    ):
        result.critical_errors.append(
            "Record is not a dictionary."
        )

        return result

    # -----------------------------------------------------
    # Required fields
    # -----------------------------------------------------

    for field_name in REQUIRED_FIELDS:

        if not _has_value(
            activity.get(
                field_name
            )
        ):
            result.critical_errors.append(
                (
                    "Missing required field: "
                    f"{field_name}."
                )
            )

    # -----------------------------------------------------
    # Day
    # -----------------------------------------------------

    day = activity.get(
        "day"
    )

    if (
        _has_value(day)
        and day not in VALID_DAYS
    ):
        result.critical_errors.append(
            f"Invalid day value: {day!r}."
        )

    # -----------------------------------------------------
    # Start time
    # -----------------------------------------------------

    start_time = activity.get(
        "start_time"
    )

    parsed_start = None

    if _has_value(
        start_time
    ):
        parsed_start = _parse_time(
            start_time
        )

        if parsed_start is None:
            result.critical_errors.append(
                (
                    "Invalid start_time: "
                    f"{start_time!r}."
                )
            )

    # -----------------------------------------------------
    # End time
    # -----------------------------------------------------

    end_time = activity.get(
        "end_time"
    )

    parsed_end = None

    if _has_value(
        end_time
    ):
        parsed_end = _parse_time(
            end_time
        )

        if parsed_end is None:
            result.critical_errors.append(
                (
                    "Invalid end_time: "
                    f"{end_time!r}."
                )
            )

    # -----------------------------------------------------
    # Time relationship
    # -----------------------------------------------------

    if (
        parsed_start is not None
        and parsed_end is not None
        and parsed_end < parsed_start
    ):
        result.warnings.append(
            (
                "end_time is earlier "
                "than start_time."
            )
        )

    # -----------------------------------------------------
    # Name
    # -----------------------------------------------------

    name = activity.get(
        "name"
    )

    if (
        isinstance(
            name,
            str,
        )
        and len(
            name.strip()
        ) > 160
    ):
        result.warnings.append(
            (
                "Activity name is "
                "unusually long."
            )
        )

    # -----------------------------------------------------
    # Age
    # -----------------------------------------------------

    min_age = activity.get(
        "min_age"
    )

    max_age = activity.get(
        "max_age"
    )

    for field_name, value in (
        (
            "min_age",
            min_age,
        ),
        (
            "max_age",
            max_age,
        ),
    ):

        if value is None:
            continue

        if not isinstance(
            value,
            int,
        ):
            result.critical_errors.append(
                (
                    f"{field_name} must be "
                    "an integer or None."
                )
            )

        elif (
            value < 0
            or value > 120
        ):
            result.critical_errors.append(
                (
                    "Unreasonable "
                    f"{field_name}: {value}."
                )
            )

    if (
        isinstance(
            min_age,
            int,
        )
        and isinstance(
            max_age,
            int,
        )
        and min_age > max_age
    ):
        result.critical_errors.append(
            (
                "min_age is greater "
                "than max_age."
            )
        )

    # -----------------------------------------------------
    # Capacity
    # -----------------------------------------------------

    capacity = activity.get(
        "capacity"
    )

    if capacity is not None:

        if not isinstance(
            capacity,
            int,
        ):
            result.critical_errors.append(
                (
                    "capacity must be "
                    "an integer or None."
                )
            )

        elif capacity < 0:
            result.critical_errors.append(
                (
                    "capacity cannot "
                    "be negative."
                )
            )

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    status = activity.get(
        "status"
    )

    if (
        _has_value(status)
        and status
        not in VALID_STATUSES
    ):
        result.warnings.append(
            (
                "Unexpected status "
                f"value: {status!r}."
            )
        )

    # -----------------------------------------------------
    # Source language
    # -----------------------------------------------------

    source_language = activity.get(
        "source_language"
    )

    if (
        _has_value(
            source_language
        )
        and source_language
        not in VALID_SOURCE_LANGUAGES
    ):
        result.warnings.append(
            (
                "Unexpected "
                "source_language: "
                f"{source_language!r}."
            )
        )

    # -----------------------------------------------------
    # End-time source
    # -----------------------------------------------------

    end_time_source = activity.get(
        "end_time_source"
    )

    if (
        _has_value(
            end_time_source
        )
        and end_time_source
        not in VALID_END_TIME_SOURCES
    ):
        result.warnings.append(
            (
                "Unexpected "
                "end_time_source: "
                f"{end_time_source!r}."
            )
        )

    if (
        end_time is None
        and end_time_source
        == "explicit"
    ):
        result.warnings.append(
            (
                "end_time_source is explicit "
                "but end_time is missing."
            )
        )

    if (
        end_time is not None
        and end_time_source
        == "missing"
    ):
        result.warnings.append(
            (
                "end_time exists but "
                "end_time_source is missing."
            )
        )

    return result


# ---------------------------------------------------------
# Full result validation
# ---------------------------------------------------------


def validate_activities(
    activities: list[
        dict[str, Any]
    ],
) -> ValidationReport:
    """
    בודק רשימה של פעילויות
    ומחזיר דוח מסכם.
    """

    records: list[
        ActivityValidation
    ] = []

    critical_errors: list[
        str
    ] = []

    warnings: list[
        str
    ] = []

    seen: set[
        tuple[Any, ...]
    ] = set()

    duplicate_count = 0

    for index, activity in enumerate(
        activities
    ):

        record = validate_activity(
            activity,
            index=index,
        )

        records.append(
            record
        )

        for error in (
            record.critical_errors
        ):
            critical_errors.append(
                (
                    f"record[{index}]: "
                    f"{error}"
                )
            )

        for warning in (
            record.warnings
        ):
            warnings.append(
                (
                    f"record[{index}]: "
                    f"{warning}"
                )
            )

        if isinstance(
            activity,
            dict,
        ):
            key = _activity_key(
                activity
            )

            if key in seen:
                duplicate_count += 1

            else:
                seen.add(
                    key
                )

    valid_records = sum(
        1
        for record in records
        if record.is_valid
    )

    invalid_records = (
        len(records)
        - valid_records
    )

    if duplicate_count:
        warnings.append(
            (
                f"Detected "
                f"{duplicate_count} "
                "duplicate record(s)."
            )
        )

    if not activities:
        warnings.append(
            "No activities were extracted."
        )

    return ValidationReport(
        total_records=len(
            records
        ),
        valid_records=valid_records,
        invalid_records=invalid_records,
        duplicate_count=duplicate_count,
        critical_errors=critical_errors,
        warnings=warnings,
        records=records,
    )


# ---------------------------------------------------------
# Keep only valid records
# ---------------------------------------------------------


def keep_valid_activities(
    activities: list[
        dict[str, Any]
    ],
    report: ValidationReport
    | None = None,
) -> list[
    dict[str, Any]
]:
    """
    מחזיר רק פעילויות
    ללא שגיאות קריטיות.
    """

    if report is None:
        report = validate_activities(
            activities
        )

    return [
        activity
        for activity, record in zip(
            activities,
            report.records,
            strict=False,
        )
        if record.is_valid
    ]
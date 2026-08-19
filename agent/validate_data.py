from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from tools import activities


BASE_DIR = Path(__file__).resolve().parent

REPORT_FILE = (
    BASE_DIR
    / "data_validation_report.json"
)


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


# ---------------------------------------------------------
# Terminal
# ---------------------------------------------------------

def _ensure_utf8_stdout() -> None:
    """
    מאפשר הצגת עברית תקינה ב-Windows Terminal.
    """

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
# Basic helpers
# ---------------------------------------------------------

def _is_empty(
    value: Any,
) -> bool:
    """
    בודק אם ערך חסר או ריק.
    """

    if value is None:
        return True

    if isinstance(
        value,
        str,
    ):
        return not value.strip()

    return False


def _parse_time(
    value: Any,
):
    """
    ממיר ערך זמן ל-time.

    מחזיר None אם הפורמט אינו תקין.
    """

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    formats = [
        "%H:%M",
        "%H:%M:%S",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                text,
                fmt,
            ).time()

        except ValueError:
            pass

    return None


def _normalize_text(
    value: Any,
) -> str:
    """
    נרמול טקסט לצורך זיהוי כפילויות.
    """

    if value is None:
        return ""

    text = (
        str(value)
        .strip()
        .casefold()
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def _safe_int(
    value: Any,
) -> int | None:
    """
    מנסה להמיר ערך למספר שלם.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _activity_label(
    activity: dict[str, Any],
    index: int,
) -> str:
    """
    תיאור קצר של פעילות לצורך הדוח.
    """

    name = (
        activity.get(
            "name"
        )
        or "ללא שם"
    )

    center = (
        activity.get(
            "center_name"
        )
        or "ללא מרכז"
    )

    day = (
        activity.get(
            "day"
        )
        or "ללא יום"
    )

    start_time = (
        activity.get(
            "start_time"
        )
        or "ללא שעה"
    )

    return (
        f"#{index + 1} | "
        f"{name} | "
        f"{center} | "
        f"{day} {start_time}"
    )


# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

def validate_activity(
    activity: dict[str, Any],
    index: int,
) -> tuple[
    list[str],
    list[str],
]:
    """
    בודק פעילות אחת.

    errors:
    בעיות שעלולות לשבור חיפוש
    או להעיד על דאטה לא תקין.

    warnings:
    מידע חסר שמותר מבחינת המערכת,
    אך חשוב לדעת עליו.
    """

    errors: list[str] = []
    warnings: list[str] = []

    label = (
        _activity_label(
            activity,
            index,
        )
    )

    # -----------------------------------------------------
    # Record type
    # -----------------------------------------------------

    if not isinstance(
        activity,
        dict,
    ):

        errors.append(
            f"{label}: "
            f"הרשומה אינה dictionary."
        )

        return (
            errors,
            warnings,
        )

    # -----------------------------------------------------
    # Required: name
    # -----------------------------------------------------

    name = activity.get(
        "name"
    )

    if _is_empty(
        name
    ):

        errors.append(
            f"{label}: "
            f"חסר name."
        )

    # -----------------------------------------------------
    # Required: center
    # -----------------------------------------------------

    center_name = (
        activity.get(
            "center_name"
        )
    )

    if _is_empty(
        center_name
    ):

        errors.append(
            f"{label}: "
            f"חסר center_name."
        )

    # -----------------------------------------------------
    # Required: day
    # -----------------------------------------------------

    day = activity.get(
        "day"
    )

    if _is_empty(
        day
    ):

        errors.append(
            f"{label}: "
            f"חסר day."
        )

    elif str(
        day
    ).strip() not in VALID_DAYS:

        errors.append(
            f"{label}: "
            f"יום לא תקין: "
            f"{day!r}."
        )

    # -----------------------------------------------------
    # Required: start time
    # -----------------------------------------------------

    start_time_raw = (
        activity.get(
            "start_time"
        )
    )

    start_time = (
        _parse_time(
            start_time_raw
        )
    )

    if _is_empty(
        start_time_raw
    ):

        errors.append(
            f"{label}: "
            f"חסרה start_time."
        )

    elif start_time is None:

        errors.append(
            f"{label}: "
            f"start_time בפורמט לא תקין: "
            f"{start_time_raw!r}."
        )

    # -----------------------------------------------------
    # End time
    # -----------------------------------------------------

    end_time_raw = (
        activity.get(
            "end_time"
        )
    )

    end_time = (
        _parse_time(
            end_time_raw
        )
    )

    if _is_empty(
        end_time_raw
    ):

        warnings.append(
            f"{label}: "
            f"חסרה end_time."
        )

    elif end_time is None:

        errors.append(
            f"{label}: "
            f"end_time בפורמט לא תקין: "
            f"{end_time_raw!r}."
        )

    elif (
        start_time is not None
        and end_time
        <= start_time
    ):

        warnings.append(
            f"{label}: "
            f"שעת הסיום "
            f"{end_time_raw} "
            f"אינה מאוחרת משעת ההתחלה "
            f"{start_time_raw}."
        )

    # -----------------------------------------------------
    # Ages
    # -----------------------------------------------------

    min_age_raw = (
        activity.get(
            "min_age"
        )
    )

    max_age_raw = (
        activity.get(
            "max_age"
        )
    )

    min_age = (
        _safe_int(
            min_age_raw
        )
        if min_age_raw is not None
        else None
    )

    max_age = (
        _safe_int(
            max_age_raw
        )
        if max_age_raw is not None
        else None
    )

    if (
        min_age_raw is not None
        and min_age is None
    ):

        errors.append(
            f"{label}: "
            f"min_age אינו מספר: "
            f"{min_age_raw!r}."
        )

    if (
        max_age_raw is not None
        and max_age is None
    ):

        errors.append(
            f"{label}: "
            f"max_age אינו מספר: "
            f"{max_age_raw!r}."
        )

    if (
        min_age is not None
        and not (
            0
            <= min_age
            <= 120
        )
    ):

        errors.append(
            f"{label}: "
            f"min_age לא סביר: "
            f"{min_age}."
        )

    if (
        max_age is not None
        and not (
            0
            <= max_age
            <= 120
        )
    ):

        errors.append(
            f"{label}: "
            f"max_age לא סביר: "
            f"{max_age}."
        )

    if (
        min_age is not None
        and max_age is not None
        and min_age > max_age
    ):

        errors.append(
            f"{label}: "
            f"min_age={min_age} "
            f"גדול מ-max_age={max_age}."
        )

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    status = (
        activity.get(
            "status"
        )
    )

    if not _is_empty(
        status
    ):

        normalized_status = (
            str(status)
            .strip()
            .casefold()
        )

        if (
            normalized_status
            not in VALID_STATUSES
        ):

            warnings.append(
                f"{label}: "
                f"status לא מוכר: "
                f"{status!r}."
            )

    # -----------------------------------------------------
    # Optional fields
    # -----------------------------------------------------

    if _is_empty(
        activity.get(
            "instructor"
        )
    ):

        warnings.append(
            f"{label}: "
            f"לא צוין instructor."
        )

    if _is_empty(
        activity.get(
            "location"
        )
    ):

        warnings.append(
            f"{label}: "
            f"לא צוין location."
        )

    if (
        min_age is None
        and max_age is None
    ):

        # זה תקין במערכת,
        # ולכן אינו warning ברמת פעילות.
        # נספור אותו בסטטיסטיקה בלבד.
        pass

    return (
        errors,
        warnings,
    )


# ---------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------

def find_duplicates(
    data: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:
    """
    מחפש רשומות שנראות זהות.

    המרכז נכלל במפתח,
    כדי ששיעור זהה בשני מרכזים שונים
    לא ייחשב כפילות.
    """

    groups: dict[
        tuple[str, ...],
        list[int],
    ] = {}

    for index, activity in enumerate(
        data
    ):

        key = (
            _normalize_text(
                activity.get(
                    "center_name"
                )
            ),
            _normalize_text(
                activity.get(
                    "branch"
                )
            ),
            _normalize_text(
                activity.get(
                    "day"
                )
            ),
            _normalize_text(
                activity.get(
                    "start_time"
                )
            ),
            _normalize_text(
                activity.get(
                    "end_time"
                )
            ),
            _normalize_text(
                activity.get(
                    "name"
                )
            ),
            _normalize_text(
                activity.get(
                    "instructor"
                )
            ),
            _normalize_text(
                activity.get(
                    "location"
                )
            ),
        )

        groups.setdefault(
            key,
            [],
        ).append(
            index
        )

    duplicates: list[
        dict[str, Any]
    ] = []

    for indices in groups.values():

        if len(
            indices
        ) <= 1:
            continue

        duplicates.append(
            {
                "indices": [
                    index + 1
                    for index in indices
                ],
                "records": [
                    _activity_label(
                        data[index],
                        index,
                    )
                    for index in indices
                ],
            }
        )

    return duplicates


# ---------------------------------------------------------
# Dataset statistics
# ---------------------------------------------------------

def build_statistics(
    data: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    """
    יוצר תמונת מצב של הדאטה.
    """

    centers = Counter()

    days = Counter()

    statuses = Counter()

    audience = Counter()

    missing_instructor = 0
    missing_location = 0
    missing_age = 0
    missing_end_time = 0

    for activity in data:

        center = (
            activity.get(
                "center_name"
            )
        )

        if not _is_empty(
            center
        ):
            centers[
                str(center)
            ] += 1

        day = (
            activity.get(
                "day"
            )
        )

        if not _is_empty(
            day
        ):
            days[
                str(day)
            ] += 1

        status = (
            activity.get(
                "status"
            )
        )

        if _is_empty(
            status
        ):
            statuses[
                "missing"
            ] += 1

        else:
            statuses[
                str(status)
            ] += 1

        target_audience = (
            activity.get(
                "target_audience"
            )
        )

        if _is_empty(
            target_audience
        ):
            audience[
                "missing"
            ] += 1

        else:
            audience[
                str(
                    target_audience
                )
            ] += 1

        if _is_empty(
            activity.get(
                "instructor"
            )
        ):
            missing_instructor += 1

        if _is_empty(
            activity.get(
                "location"
            )
        ):
            missing_location += 1

        if (
            activity.get(
                "min_age"
            ) is None
            and activity.get(
                "max_age"
            ) is None
        ):
            missing_age += 1

        if _is_empty(
            activity.get(
                "end_time"
            )
        ):
            missing_end_time += 1

    return {
        "total_activities":
            len(
                data
            ),

        "centers":
            dict(
                sorted(
                    centers.items()
                )
            ),

        "days":
            dict(
                sorted(
                    days.items()
                )
            ),

        "statuses":
            dict(
                sorted(
                    statuses.items()
                )
            ),

        "target_audience":
            dict(
                sorted(
                    audience.items()
                )
            ),

        "missing_optional_fields": {
            "instructor":
                missing_instructor,

            "location":
                missing_location,

            "age_range":
                missing_age,

            "end_time":
                missing_end_time,
        },
    }


# ---------------------------------------------------------
# Main validation
# ---------------------------------------------------------

def main() -> None:

    _ensure_utf8_stdout()

    print()
    print(
        "=" * 72
    )

    print(
        "Community Center AI Agent - Data Validation"
    )

    print(
        "=" * 72
    )

    print(
        f"Activities loaded: "
        f"{len(activities)}"
    )

    print()

    # -----------------------------------------------------
    # General dataset check
    # -----------------------------------------------------

    if not activities:

        print(
            "ERROR ❌"
        )

        print(
            "לא נטענו פעילויות."
        )

        return

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # -----------------------------------------------------
    # Validate records
    # -----------------------------------------------------

    for index, activity in enumerate(
        activities
    ):

        errors, warnings = (
            validate_activity(
                activity,
                index,
            )
        )

        all_errors.extend(
            errors
        )

        all_warnings.extend(
            warnings
        )

    # -----------------------------------------------------
    # Duplicates
    # -----------------------------------------------------

    duplicates = (
        find_duplicates(
            activities
        )
    )

    # -----------------------------------------------------
    # Statistics
    # -----------------------------------------------------

    statistics = (
        build_statistics(
            activities
        )
    )

    # -----------------------------------------------------
    # Errors
    # -----------------------------------------------------

    print(
        "=== ERRORS ==="
    )

    if all_errors:

        for error in all_errors:

            print(
                "❌",
                error,
            )

    else:

        print(
            "✅ No critical data errors found."
        )

    print()

    # -----------------------------------------------------
    # Duplicates
    # -----------------------------------------------------

    print(
        "=== POSSIBLE DUPLICATES ==="
    )

    if duplicates:

        for duplicate_number, duplicate in enumerate(
            duplicates,
            start=1,
        ):

            print(
                f"⚠ Duplicate group "
                f"{duplicate_number}:"
            )

            for record in (
                duplicate[
                    "records"
                ]
            ):

                print(
                    "   -",
                    record,
                )

    else:

        print(
            "✅ No duplicate activities found."
        )

    print()

    # -----------------------------------------------------
    # Warnings
    # -----------------------------------------------------

    print(
        "=== WARNINGS ==="
    )

    if all_warnings:

        print(
            f"Found {len(all_warnings)} "
            f"non-critical warnings."
        )

        # כדי לא להציף את הטרמינל,
        # מציגים עד 20 דוגמאות.
        for warning in (
            all_warnings[:20]
        ):

            print(
                "⚠",
                warning,
            )

        if (
            len(
                all_warnings
            )
            > 20
        ):

            print(
                f"... and "
                f"{len(all_warnings) - 20} "
                f"more warnings."
            )

    else:

        print(
            "✅ No warnings found."
        )

    print()

    # -----------------------------------------------------
    # Statistics
    # -----------------------------------------------------

    print(
        "=== DATA STATISTICS ==="
    )

    print(
        "Total activities:",
        statistics[
            "total_activities"
        ],
    )

    print()

    print(
        "Activities per day:"
    )

    for day, count in (
        statistics[
            "days"
        ].items()
    ):

        print(
            f"  {day}: {count}"
        )

    print()

    print(
        "Activities per center:"
    )

    for center, count in (
        statistics[
            "centers"
        ].items()
    ):

        print(
            f"  {center}: {count}"
        )

    print()

    missing = (
        statistics[
            "missing_optional_fields"
        ]
    )

    print(
        "Missing optional information:"
    )

    print(
        "  instructor:",
        missing[
            "instructor"
        ],
    )

    print(
        "  location:",
        missing[
            "location"
        ],
    )

    print(
        "  age range:",
        missing[
            "age_range"
        ],
    )

    print(
        "  end_time:",
        missing[
            "end_time"
        ],
    )

    # -----------------------------------------------------
    # Final status
    # -----------------------------------------------------

    print()
    print(
        "=" * 72
    )

    print(
        "FINAL DATA VALIDATION"
    )

    print(
        "=" * 72
    )

    print(
        "CRITICAL ERRORS:",
        len(
            all_errors
        ),
    )

    print(
        "WARNINGS:",
        len(
            all_warnings
        ),
    )

    print(
        "DUPLICATE GROUPS:",
        len(
            duplicates
        ),
    )

    if not all_errors:

        print(
            "STATUS: PASS ✅"
        )

    else:

        print(
            "STATUS: FAIL ❌"
        )

    print(
        "=" * 72
    )

    # -----------------------------------------------------
    # Save report
    # -----------------------------------------------------

    report = {
        "summary": {
            "total_activities":
                len(
                    activities
                ),

            "critical_errors":
                len(
                    all_errors
                ),

            "warnings":
                len(
                    all_warnings
                ),

            "duplicate_groups":
                len(
                    duplicates
                ),

            "status": (
                "PASS"
                if not all_errors
                else "FAIL"
            ),
        },

        "statistics":
            statistics,

        "errors":
            all_errors,

        "warnings":
            all_warnings,

        "duplicates":
            duplicates,
    }

    with REPORT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()

    print(
        "Report saved to:"
    )

    print(
        REPORT_FILE
    )


if __name__ == "__main__":
    main()
# =========================================================
# זרימת קליטת הנתונים
# =========================================================
#
# מטרה:
# לקבל קובץ חדש, לנתח אותו, לבדוק את איכות הנתונים,
# ולוודא שהתוצאה אמינה לפני שהיא מועברת לשכבת השמירה.
#
#
# 1. קבלת הקובץ
# ---------------------------------------------------------
#
# File
#
# המערכת מקבלת קובץ חדש ממקור הנתונים.
#
#
# 2. קריאת הקובץ
# ---------------------------------------------------------
#
# Reader
#
# הקובץ נקרא והתוכן הגולמי מחולץ ממנו.
#
# התוכן יכול לכלול:
# טקסט.
# פסקאות.
# טבלאות.
# מבנים שונים של מידע.
#
# בשלב זה עדיין לא מתקבלת החלטה
# לגבי מבנה הפעילויות.
#
#
# 3. ניסיון ניתוח באמצעות Parsers קבועים
# ---------------------------------------------------------
#
# Basic Parser
#
# Table Parser
#
# Dirty Parser
#
# Bilingual Parser
#
# Grouped Parser
#
# Edge Case Parser
#
# כל Parser מנסה לנתח את אותו קובץ
# לפי מבנה שהוא יודע לזהות.
#
# כל Parser יכול להחזיר
# רשימת פעילויות אפשרית משלו.
#
#
# 4. תקנון והסרת כפילויות
# ---------------------------------------------------------
#
# Normalization
#
# Deduplication
#
# תוצאות ה-Parsers עוברות תקנון
# לפורמט האחיד של המערכת.
#
# לדוגמה:
# שמות ימים בפורמט אחיד.
# שעות בפורמט אחיד.
# קהל יעד בפורמט אחיד.
# שדות נוספים בהתאם למבנה הנתונים.
#
# בנוסף,
# רשומות כפולות בתוך תוצאת הניתוח
# מוסרות לפני הערכת התוצאה.
#
#
# 5. הערכת איכות ובדיקת תקינות
# ---------------------------------------------------------
#
# Quality Score
#
# Validation
#
# כל תוצאה מקבלת ציון איכות
# ועוברת בדיקות דטרמיניסטיות באמצעות Python.
#
# נבדקים בין היתר:
# שדות מרכזיים.
# שדות חסרים.
# תקינות הימים.
# תקינות השעות.
# טווחי גיל.
# סטטוס הפעילות.
# מספר הרשומות התקינות.
# שגיאות קריטיות.
# אזהרות.
#
# מטרת שלב זה היא לבדוק
# האם תוצאת ה-Parser מספיק אמינה
# כדי להמשיך איתה.
#
#
# 6. השוואה ובחירת התוצאה
# ---------------------------------------------------------
#
# המערכת משווה בין התוצאות
# של כל ה-Parsers.
#
# אם קיימת תוצאה אחת חזקה וברורה,
# שעברה את ה-Validation
# ועומדת בסף האיכות,
# ניתן לבחור בה ללא שימוש נוסף במודל שפה.
#
# אם אין תוצאה אמינה,
# עוברים ל-LLM Fallback.
#
# אם קיימות כמה תוצאות חזקות
# שהציונים שלהן קרובים,
# עוברים לבדיקה סמנטית נוספת.
#
#
# 7. בדיקה סמנטית במקרה של אי-ודאות
# ---------------------------------------------------------
#
# LLM Verifier
#
# מודל השפה מקבל:
# את תוכן הקובץ המקורי.
# ואת תוצאות ה-Parsers החזקות ביותר.
#
# הוא משווה ביניהן ובודק
# איזו תוצאה מייצגת בצורה המדויקת ביותר
# את המידע שמופיע במקור.
#
# ה-Verifier אינו יוצר פעילויות חדשות.
#
# הוא משמש כשכבת בדיקה סמנטית
# כאשר הבדיקות הדטרמיניסטיות לבדן
# אינן מספיקות כדי לבחור בין התוצאות.
#
#
# 8. ניסיון חלופי כאשר אין Parser אמין
# ---------------------------------------------------------
#
# LLM Fallback
#
# אם אף אחד מה-Parsers הקבועים
# לא מחזיר תוצאה אמינה,
# המערכת משתמשת במודל השפה
# כדי לנתח את המסמך באופן כללי יותר.
#
# גם תוצאת ה-Fallback
# מוחזרת לפי המבנה האחיד של הפרויקט
# ועוברת תקנון והסרת כפילויות
# כחלק מתהליך הניתוח שלה.
#
#
# 9. בדיקה סופית
# ---------------------------------------------------------
#
# Final Validation
#
# לפני שהתוצאה נחשבת מוכנה,
# היא עוברת Validation דטרמיניסטי נוסף.
#
# שלב זה מתבצע גם כאשר התוצאה
# הגיעה מ-Parser קבוע
# וגם כאשר היא הגיעה מ-LLM Fallback.
#
# אם הבדיקה הסופית נכשלת,
# התוצאה אינה מתקבלת כתוצאה תקינה.
#
# אף Parser ואף מודל שפה
# אינם שומרים מידע ישירות בבסיס הנתונים.
#
#
# 10. הנתונים מוכנים לשכבת השמירה
# ---------------------------------------------------------
#
# Supabase
#
# לאחר שהפעילויות עברו:
# ניתוח.
# תקנון.
# הסרת כפילויות.
# הערכת איכות.
# Validation.
# ובמידת הצורך גם בדיקה סמנטית.
#
# הן מוכנות לעבור לשכבת ה-Ingestion
# שאחראית על השמירה ב-Supabase.
#
#
# =========================================================
# זרימה מקוצרת
# =========================================================
#
# File
#   ↓
# Reader
#   ↓
# Known Parsers
#   ↓
# Normalization + Deduplication
#   ↓
# Quality Score + Validation
#   ↓
# בחירת התוצאה
#
# אם קיימות כמה תוצאות קרובות:
#
# LLM Verifier
#
# אם אין Parser אמין:
#
# LLM Fallback
#
#   ↓
# Final Validation
#   ↓
# Ready for Ingestion
#   ↓
# Supabase
#
#
# עיקרון מרכזי:
#
# Python אחראית על בדיקות
# דטרמיניסטיות, טכניות ולוגיות.
#
# מודל השפה משמש להבנה סמנטית
# כאשר קיימת אי-ודאות,
# או כ-Fallback כאשר המבנה
# אינו מתאים ל-Parsers הקבועים.
#
# שום מידע אינו נחשב מוכן לשמירה
# לפני שעבר Final Validation.
# =========================================================

"""
הקובץ מנהל את תהליך הפענוח של מסמכי המקור

הוא מפעיל את דרכי הפענוח השונות
משווה בין התוצאות לפי איכות ותקינות
ובוחר את הדרך האמינה ביותר

כאשר קיימת אי ודאות ניתן להשתמש בבדיקת מודל שפה
וכאשר אין תוצאה אמינה המערכת עוברת לפענוח חלופי
"""
from __future__ import annotations
from ingestion.generic_llm_parser import (
    parse_generic_schedule,
)
from ingestion.llm_verifier import (
    verify_parser_candidates,
)
from ingestion.validation import (
    validate_activities,
)

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ingestion.parsers.schedule_parsers import (
    parse_basic_schedule,
    parse_table_schedule,
    parse_dirty_schedule,
    parse_bilingual_schedule,
    parse_grouped_schedule,
    parse_edge_case_schedule,
)


ParserFunction = Callable[
    [Path],
    list[dict[str, Any]],
]


PARSERS: dict[
    str,
    ParserFunction,
] = {
    "basic": parse_basic_schedule,
    "table": parse_table_schedule,
    "dirty": parse_dirty_schedule,
    "bilingual": parse_bilingual_schedule,
    "grouped": parse_grouped_schedule,
    "edge_case": parse_edge_case_schedule,
}


VALID_DAYS = {
    "ראשון",
    "שני",
    "שלישי",
    "רביעי",
    "חמישי",
    "שישי",
    "שבת",
}


CORE_FIELDS = (
    "name",
    "day",
    "start_time",
    "center_name",
)


OPTIONAL_QUALITY_FIELDS = (
    "end_time",
    "instructor",
    "location",
    "target_audience",
)


TIME_PATTERN = re.compile(
    r"^\d{2}:\d{2}$"
)


MIN_ACTIVITY_QUALITY = 0.60

MIN_PARSER_SCORE = 0.78
VERIFICATION_SCORE_MARGIN = 0.05


@dataclass
class ParserAttempt:
    parser_name: str
    activities: list[dict[str, Any]]
    score: float
    valid_count: int
    total_count: int
    validation_passed: bool = False
    critical_error_count: int = 0
    warning_count: int = 0

    error: str | None = None


def _has_value(
    value: Any,
) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(
            value.strip()
        )

    return True


def _activity_quality(
    activity: dict[str, Any],
) -> float:
    """
    Calculates how structurally valid one extracted
    activity looks.

    This does not decide whether the information is
    factually correct. It checks whether the parser
    produced a useful record in the expected schema.
    """

    if not isinstance(
        activity,
        dict,
    ):
        return 0.0

    # --------------------------------------------------
    # Core schema completeness
    # --------------------------------------------------

    core_present = sum(
        1
        for field in CORE_FIELDS
        if _has_value(
            activity.get(field)
        )
    )

    core_score = (
        core_present
        / len(CORE_FIELDS)
    )

    # --------------------------------------------------
    # Optional useful fields
    # --------------------------------------------------

    optional_present = sum(
        1
        for field in OPTIONAL_QUALITY_FIELDS
        if _has_value(
            activity.get(field)
        )
    )

    optional_score = (
        optional_present
        / len(OPTIONAL_QUALITY_FIELDS)
    )

    # --------------------------------------------------
    # Semantic sanity checks
    # --------------------------------------------------

    semantic_checks = 0
    semantic_passed = 0

    day = activity.get(
        "day"
    )

    if _has_value(day):
        semantic_checks += 1

        if day in VALID_DAYS:
            semantic_passed += 1

    start_time = activity.get(
        "start_time"
    )

    if _has_value(start_time):
        semantic_checks += 1

        if (
            isinstance(
                start_time,
                str,
            )
            and TIME_PATTERN.match(
                start_time
            )
        ):
            semantic_passed += 1

    name = activity.get(
        "name"
    )

    if _has_value(name):
        semantic_checks += 1

        if (
            isinstance(
                name,
                str,
            )
            and 1
            <= len(name.strip())
            <= 120
        ):
            semantic_passed += 1

    semantic_score = (
        semantic_passed
        / semantic_checks
        if semantic_checks
        else 0.0
    )

    # Core fields have the highest importance.
    return (
        core_score * 0.65
        + optional_score * 0.15
        + semantic_score * 0.20
    )
# These weights were manually chosen:
# 65% for core fields, 15% for optional fields,
# and 20% for semantic sanity checks.


# Example:
# Activity:
# {
#     "name": "פילאטיס",
#     "day": "שלישי",
#     "start_time": "18:00",
#     "center_name": "מרכז הדס",
#
#     "end_time": "19:00",
#     "instructor": "משה",
#     "location": None,
#     "target_audience": None,
# }
#
# Core fields:     4/4 = 1.0   -> 1.0 * 0.65 = 0.65
# Optional fields: 2/4 = 0.5   -> 0.5 * 0.15 = 0.075
# Semantic checks: 3/3 = 1.0   -> 1.0 * 0.20 = 0.20
#
# Final quality score:
# 0.65 + 0.075 + 0.20 = 0.925
#
# Since 0.925 >= MIN_ACTIVITY_QUALITY (0.60),
# this activity is considered structurally valid.
#
# Note: this score measures structural quality,
# not whether the extracted information is factually correct.


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    Used only to remove duplicate records produced
    by the same parser attempt.
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


def _deduplicate(
    activities: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:
    seen: set[
        tuple[Any, ...]
    ] = set()

    unique: list[
        dict[str, Any]
    ] = []

    for activity in activities:
        key = _activity_key(
            activity
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            activity
        )

    return unique

def _final_validate(
    activities: list[
        dict[str, Any]
    ],
    *,
    source_name: str,
) -> list[
    dict[str, Any]
]:
    """
    Final deterministic validation gate.

    No parser or LLM result is accepted
    before passing this validation.
    """

    report = validate_activities(
        activities
    )

    print(
        "[universal_docx_parser] "
        f"Final validation for "
        f"{source_name}: "
        f"{'PASS' if report.passed else 'FAIL'}"
    )

    print(
        "[universal_docx_parser] "
        f"Final validation records: "
        f"{report.valid_records}/"
        f"{report.total_records}"
    )

    print(
        "[universal_docx_parser] "
        f"Critical errors: "
        f"{len(report.critical_errors)} "
        f"| warnings: "
        f"{len(report.warnings)}"
    )

    if not report.passed:

        for error in (
            report.critical_errors[:5]
        ):
            print(
                "[universal_docx_parser] "
                f"Validation error: {error}"
            )

        return []

    return activities

def _score_parser_result(
    activities: list[
        dict[str, Any]
    ],
) -> tuple[
    float,
    int,
]:
    """
    Scores the complete result of one parser.

    We consider:
    - quality of individual records
    - percentage of useful records
    - number of valid activities extracted
    """

    if not activities:
        return (
            0.0,
            0,
        )

    qualities = [
        _activity_quality(
            activity
        )
        for activity in activities
    ]

    valid_qualities = [
        quality
        for quality in qualities
        if quality
        >= MIN_ACTIVITY_QUALITY
    ]

    valid_count = len(
        valid_qualities
    )

    if valid_count == 0:
        return (
            0.0,
            0,
        )

    average_quality = (
        sum(valid_qualities)
        / valid_count
    )

    valid_ratio = (
        valid_count
        / len(activities)
    )

    # Five or more good activities is a strong signal.
    # This reaches 1.0 at eight valid activities.
    count_signal = min(
        valid_count / 8.0,
        1.0,
    )

    score = (
        average_quality * 0.45
        + valid_ratio * 0.20
        + count_signal * 0.35
    )

    return (
        score,
        valid_count,
    )


def _try_parser(
    parser_name: str,
    parser: ParserFunction,
    file_path: Path,
) -> ParserAttempt:
    """
    Runs one parser safely.

    A parser that cannot understand this document is
    allowed to fail without stopping the whole pipeline.
    """

    try:
        activities = parser(
            file_path
        )

        if not isinstance(
            activities,
            list,
        ):
            return ParserAttempt(
                parser_name=parser_name,
                activities=[],
                score=0.0,
                valid_count=0,
                total_count=0,
                error=(
                    "Parser did not return a list."
                ),
            )

        activities = _deduplicate(
            activities
        )

        score, valid_count = (
            _score_parser_result(
                activities
            )
        )
        validation_report = (
            validate_activities(
                 activities
             )
         )

        return ParserAttempt(
            parser_name=parser_name,
            activities=activities,
            score=score,
            valid_count=valid_count,
            total_count=len(
                activities
            ),
            validation_passed=(
                validation_report.passed
            ),
            critical_error_count=len(
                 validation_report.critical_errors
            ),
            warning_count=len(
                 validation_report.warnings
            ),
            error=None,
        )

    except Exception as exc:
        return ParserAttempt(
            parser_name=parser_name,
            activities=[],
            score=0.0,
            valid_count=0,
            total_count=0,
            error=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )


def evaluate_known_parsers(
    file_path: Path,
) -> list[
    ParserAttempt
]:
    """
    Runs all known deterministic parsers against
    the same Word document.

    Results are sorted from best to worst.
    """

    attempts = [
        _try_parser(
            parser_name,
            parser,
            file_path,
        )
        for parser_name, parser
        in PARSERS.items()
    ]

    attempts.sort(
        key=lambda attempt: (
            attempt.score,
            attempt.valid_count,
        ),
        reverse=True,
    )

    return attempts

def _needs_llm_verification(
    attempts: list[
        ParserAttempt
    ],
) -> bool:
    """
    Checks whether the strongest parser results
    are close enough to require semantic verification.
    """

    eligible = [
        attempt
        for attempt in attempts
        if (
            attempt.score
            >= MIN_PARSER_SCORE
            and attempt.valid_count > 0
            and attempt.validation_passed
            and attempt.error is None
        )
    ]

    if len(eligible) < 2:
        return False

    best = eligible[0]
    second_best = eligible[1]

    score_gap = (
        best.score
        - second_best.score
    )

    return (
        score_gap
        <= VERIFICATION_SCORE_MARGIN
    )
def _build_verification_candidates(
    attempts: list[
        ParserAttempt
    ],
) -> list[
    dict[str, Any]
]:
    """
    Builds the strongest parser candidates
    for semantic LLM verification.
    """

    eligible = [
        attempt
        for attempt in attempts
        if (
            attempt.score
            >= MIN_PARSER_SCORE
            and attempt.valid_count > 0
            and attempt.validation_passed
            and attempt.error is None
        )
    ]

    if len(eligible) < 2:
        return []

    best_score = eligible[0].score

    close_attempts = [
        attempt
        for attempt in eligible
        if (
            best_score
            - attempt.score
            <= VERIFICATION_SCORE_MARGIN
        )
    ]

    return [
        {
            "parser_name":
                attempt.parser_name,

            "score":
                round(
                    attempt.score,
                    4,
                ),

            "valid_count":
                attempt.valid_count,

            "total_count":
                attempt.total_count,

            "critical_error_count":
                attempt.critical_error_count,

            "warning_count":
                attempt.warning_count,

            "activities":
                attempt.activities,
        }
        for attempt
        in close_attempts[:3]
    ]

def choose_best_known_parser(
    file_path: Path,
) -> tuple[
    ParserAttempt | None,
    list[ParserAttempt],
]:
    """
    Returns the best known parser if the result is
    strong enough.

    Otherwise returns None so the caller can use
    a generic LLM fallback.
    """

    attempts = (
        evaluate_known_parsers(
            file_path
        )
    )

    if not attempts:
        return (
            None,
            [],
        )

    eligible_attempts = [
        attempt
        for attempt in attempts
        if (
            attempt.score
            >= MIN_PARSER_SCORE
            and attempt.valid_count > 0
            and attempt.validation_passed
            and attempt.error is None
        )
    ]

    if not eligible_attempts:
        return (
            None,
            attempts,
        )

    best = eligible_attempts[0]

    return (
        best,
        attempts,
    )


def parse_with_known_parsers(
    file_path: Path,
) -> tuple[
    list[dict[str, Any]],
    str | None,
    list[ParserAttempt],
]:
    """
    Public entry point for the deterministic layer.

    If a known parser understands the file:
        activities, parser_name, attempts

    If none is reliable:
        [], None, attempts

    In the next step, None will trigger the LLM fallback.
    """

    best, attempts = (
        choose_best_known_parser(
            file_path
        )
    )

    if best is None:
        return (
            [],
            None,
            attempts,
        )

    return (
        best.activities,
        best.parser_name,
        attempts,
    )
def parse_universal_docx(
    file_path: Path,
) -> tuple[
    list[dict[str, Any]],
    str,
    list[ParserAttempt],
]:
    """
    Main universal DOCX parsing entry point.

    1. Try all known deterministic parsers.
    2. If one produces a reliable result, use it.
    3. Otherwise automatically fall back to the LLM parser.
    """

    (
        activities,
        parser_name,
        attempts,
    ) = parse_with_known_parsers(
        file_path
    )
    needs_verification = (
        _needs_llm_verification(
            attempts
        )
    )

    if needs_verification:
        print(
            "\n[universal_docx_parser] "
            "Top parser results are close."
        )

        print(
         "[universal_docx_parser] "
         "Running LLM verifier..."
        )

        verification_candidates = (
         _build_verification_candidates(
             attempts
          )
        )

        decision = (
         verify_parser_candidates(
             file_path=file_path,
             candidates=(
                 verification_candidates
             ),
         )
     )

        print(
             "[universal_docx_parser] "
             "Verifier decision:",
             decision.selected_parser,
         )

        print(
              "[universal_docx_parser] "
             "Verifier confident:",
              decision.confident,
         )

        print(
             "[universal_docx_parser] "
             "Verifier reason:",
             decision.reason,
        )

        if (
            decision.confident
            and not decision.needs_fallback
            and decision.selected_parser
            is not None
        ):
            verified_attempt = next(
             (
                   attempt
                  for attempt in attempts
                 if (
                       attempt.parser_name
                      == decision.selected_parser
                 )
             ),
              None,
            )

            if verified_attempt is not None:
                activities = (
                 verified_attempt.activities
             )

                parser_name = (
                    verified_attempt.parser_name
                )

            else:
                activities = []
                parser_name = None

        else:
            activities = []
            parser_name = None

    
    # --------------------------------------------------
    # Known deterministic parser succeeded
    # --------------------------------------------------

    if parser_name is not None:

        final_activities = (
            _final_validate(
                activities,
                source_name=parser_name,
            )
     )

        if final_activities:
         return (
             final_activities,
             parser_name,
             attempts,
         )

        print(
         "\n[universal_docx_parser] "
          "Selected parser failed "
          "final validation."
    )

        print(
         "[universal_docx_parser] "
         "Moving to generic LLM fallback..."
        )

    # --------------------------------------------------
    # No known parser was reliable -> LLM fallback
    # --------------------------------------------------

    print(
        "\n[universal_docx_parser] "
        "No reliable known parser found."
    )

    print(
        "[universal_docx_parser] "
        "Using generic LLM fallback..."
    )

    generic_activities = (
     parse_generic_schedule(
           file_path
      )
    )

    final_generic_activities = (
     _final_validate(
            generic_activities,
             source_name="generic_llm",
        )
    )

    if not final_generic_activities:
        print(
         "[universal_docx_parser] "
         "Generic LLM result failed "
         "final validation."
         )

        return (
         [],
         "generic_llm",
         attempts,
        )

    return (
     final_generic_activities,
     "generic_llm",
      attempts,
    )

def print_attempts(
    attempts: list[
        ParserAttempt
    ],
) -> None:
    """
    Debug output explaining why a parser was chosen.
    """

    print(
        "\nParser attempts:"
    )

    for attempt in attempts:
        print(
            f"- {attempt.parser_name:12} "
            f"| score={attempt.score:.3f} "
            f"| valid={attempt.valid_count} "
            f"| total={attempt.total_count}"
        )
        print(
            "  "
            f"validation="
            f"{'PASS' if attempt.validation_passed else 'FAIL'} "
            f"| critical="
            f"{attempt.critical_error_count} "
            f"| warnings="
            f"{attempt.warning_count}"
        )

        if attempt.error:
            print(
                f"  error: {attempt.error}"
            )


def main() -> None:
    import sys

    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: "
            "python -m "
            "ingestion.universal_docx_parser "
            "<path-to-docx>"
        )

    file_path = Path(
        sys.argv[1]
    )

    if not file_path.exists():
        raise FileNotFoundError(
            file_path
        )

    activities, parser_name, attempts = (
        parse_universal_docx(
            file_path
        )
    )

    print_attempts(
        attempts
    )

    print(
        "\nSelected parser:",
        parser_name
        or "NONE -> LLM fallback required",
    )

    print(
        "Activities:",
        len(activities),
    )


if __name__ == "__main__":
    main()
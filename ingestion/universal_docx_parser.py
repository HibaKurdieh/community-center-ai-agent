from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


from ingestion.parsers.basic_schedule_parser import (
    parse_basic_schedule,
)
from ingestion.parsers.table_schedule_parser import (
    parse_table_schedule,
)
from ingestion.parsers.dirty_schedule_parser import (
    parse_dirty_schedule,
)
from ingestion.parsers.bilingual_schedule_parser import (
    parse_bilingual_schedule,
)
from ingestion.parsers.grouped_schedule_parser import (
    parse_grouped_schedule,
)
from ingestion.parsers.edge_case_schedule_parser import (
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


@dataclass
class ParserAttempt:
    parser_name: str
    activities: list[dict[str, Any]]
    score: float
    valid_count: int
    total_count: int
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

        return ParserAttempt(
            parser_name=parser_name,
            activities=activities,
            score=score,
            valid_count=valid_count,
            total_count=len(
                activities
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

    best = attempts[0]

    if (
        best.score
        < MIN_PARSER_SCORE
        or best.valid_count == 0
    ):
        return (
            None,
            attempts,
        )

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
        parse_with_known_parsers(
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
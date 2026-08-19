from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from graph import graph


BASE_DIR = Path(__file__).resolve().parent

CASES_FILE = (
    BASE_DIR
    / "evaluation_cases.json"
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _normalize(
    value: Any,
) -> str:
    """
    Converts a value to normalized text
    for tolerant comparison.
    """

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .casefold()
    )


def _contains(
    actual: Any,
    expected_part: str,
) -> bool:

    return (
        _normalize(
            expected_part
        )
        in _normalize(
            actual
        )
    )


def _result_count(
    result: dict[str, Any],
) -> int:

    tool_results = (
        result.get(
            "tool_results",
            [],
        )
    )

    if not isinstance(
        tool_results,
        list,
    ):
        return 0

    return len(
        tool_results
    )


def _check_exact(
    failures: list[str],
    result: dict[str, Any],
    field: str,
    expected_value: Any,
) -> None:

    actual_value = (
        result.get(
            field
        )
    )

    if actual_value != expected_value:

        failures.append(
            f"{field}: "
            f"expected={expected_value!r}, "
            f"actual={actual_value!r}"
        )


def _check_contains_field(
    failures: list[str],
    result: dict[str, Any],
    field: str,
    expected_part: str,
) -> None:

    actual_value = (
        result.get(
            field
        )
    )

    if not _contains(
        actual_value,
        expected_part,
    ):

        failures.append(
            f"{field}: "
            f"expected to contain "
            f"{expected_part!r}, "
            f"actual={actual_value!r}"
        )


# ---------------------------------------------------------
# Single test
# ---------------------------------------------------------

def evaluate_case(
    case: dict[str, Any],
) -> dict[str, Any]:

    case_id = (
        case.get(
            "id",
            "?",
        )
    )

    query = (
        case.get(
            "query",
            "",
        )
    )

    expected = (
        case.get(
            "expected",
            {},
        )
    )

    failures: list[str] = []

    started = (
        time.perf_counter()
    )

    try:

        result = graph.invoke(
            {
                "user_message":
                    query,
            }
        )

    except Exception as error:

        duration = (
            time.perf_counter()
            - started
        )

        return {
            "id":
                case_id,

            "query":
                query,

            "passed":
                False,

            "duration":
                duration,

            "failures": [
                "Graph exception: "
                + repr(
                    error
                )
            ],

            "result":
                {},
        }

    duration = (
        time.perf_counter()
        - started
    )

    # -----------------------------------------------------
    # Exact structured fields
    # -----------------------------------------------------

    exact_fields = [
        "intent",
        "day",
        "start_after",
        "start_before",
        "target_audience",
        "age",
    ]

    for field in exact_fields:

        if field in expected:

            _check_exact(
                failures=failures,
                result=result,
                field=field,
                expected_value=(
                    expected[
                        field
                    ]
                ),
            )

    # -----------------------------------------------------
    # Tolerant text fields
    # -----------------------------------------------------

    if "category_contains" in expected:

        _check_contains_field(
            failures=failures,
            result=result,
            field="category",
            expected_part=(
                expected[
                    "category_contains"
                ]
            ),
        )

    if "center_contains" in expected:

        _check_contains_field(
            failures=failures,
            result=result,
            field="center_name",
            expected_part=(
                expected[
                    "center_contains"
                ]
            ),
        )

    if "instructor_contains" in expected:

        _check_contains_field(
            failures=failures,
            result=result,
            field="instructor",
            expected_part=(
                expected[
                    "instructor_contains"
                ]
            ),
        )

    # -----------------------------------------------------
    # Result count
    # -----------------------------------------------------

    count = (
        _result_count(
            result
        )
    )

    if "min_results" in expected:

        minimum = int(
            expected[
                "min_results"
            ]
        )

        if count < minimum:

            failures.append(
                f"result_count: "
                f"expected >= {minimum}, "
                f"actual={count}"
            )

    if "exact_results" in expected:

        exact_count = int(
            expected[
                "exact_results"
            ]
        )

        if count != exact_count:

            failures.append(
                f"result_count: "
                f"expected={exact_count}, "
                f"actual={count}"
            )

    # -----------------------------------------------------
    # Final-answer content
    # -----------------------------------------------------

    final_answer = (
        result.get(
            "final_answer"
        )
        or ""
    )

    for text in expected.get(
        "must_contain",
        [],
    ):

        if not _contains(
            final_answer,
            text,
        ):

            failures.append(
                "final_answer missing: "
                + repr(
                    text
                )
            )

    for text in expected.get(
        "must_not_contain",
        [],
    ):

        if _contains(
            final_answer,
            text,
        ):

            failures.append(
                "final_answer should not contain: "
                + repr(
                    text
                )
            )

    # -----------------------------------------------------
    # Clarification
    # -----------------------------------------------------

    if expected.get(
        "allow_clarification",
        False,
    ):

        waiting = bool(
            result.get(
                "waiting_for_clarification",
                False,
            )
        )

        intent = (
            result.get(
                "intent"
            )
        )

        # For a vague query we accept either:
        # - explicit clarification
        # - a valid activity route
        #
        # We mainly want to make sure the Agent
        # does not crash or invent another domain.

        if (
            not waiting
            and intent
            not in {
                "activity",
                "unknown",
            }
        ):

            failures.append(
                "Expected clarification "
                "or activity/unknown intent. "
                f"actual intent={intent!r}"
            )

    return {
        "id":
            case_id,

        "query":
            query,

        "passed":
            len(
                failures
            ) == 0,

        "duration":
            duration,

        "failures":
            failures,

        "result":
            result,
    }


# ---------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------

def main() -> None:

    if not CASES_FILE.exists():

        raise FileNotFoundError(
            f"Evaluation file not found: "
            f"{CASES_FILE}"
        )

    with CASES_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        cases = json.load(
            file
        )

    if not isinstance(
        cases,
        list,
    ):

        raise ValueError(
            "evaluation_cases.json "
            "must contain a JSON list."
        )

    print()
    print(
        "=" * 72
    )

    print(
        "Community Center AI Agent - Evaluation"
    )

    print(
        "=" * 72
    )

    print(
        f"Cases: {len(cases)}"
    )

    print()

    results: list[
        dict[str, Any]
    ] = []

    total_started = (
        time.perf_counter()
    )

    for index, case in enumerate(
        cases,
        start=1,
    ):

        case_id = (
            case.get(
                "id",
                f"#{index}",
            )
        )

        description = (
            case.get(
                "description",
                "",
            )
        )

        query = (
            case.get(
                "query",
                "",
            )
        )

        print(
            f"[{index}/{len(cases)}] "
            f"{case_id} - "
            f"{description}"
        )

        print(
            f"Query: {query}"
        )

        evaluation = (
            evaluate_case(
                case
            )
        )

        results.append(
            evaluation
        )

        if evaluation[
            "passed"
        ]:

            print(
                "PASS ✅"
            )

        else:

            print(
                "FAIL ❌"
            )

            for failure in (
                evaluation[
                    "failures"
                ]
            ):

                print(
                    "   - "
                    + failure
                )

        print(
            "Time: "
            f"{evaluation['duration']:.2f}s"
        )

        print(
            "-" * 72
        )

    total_duration = (
        time.perf_counter()
        - total_started
    )

    passed = sum(
        1
        for item in results
        if item[
            "passed"
        ]
    )

    failed = (
        len(
            results
        )
        - passed
    )

    percentage = (
        (
            passed
            / len(
                results
            )
        )
        * 100
        if results
        else 0
    )

    print()
    print(
        "=" * 72
    )

    print(
        "FINAL RESULTS"
    )

    print(
        "=" * 72
    )

    print(
        f"PASS: {passed}"
    )

    print(
        f"FAIL: {failed}"
    )

    print(
        f"TOTAL: {len(results)}"
    )

    print(
        f"SCORE: {percentage:.1f}%"
    )

    print(
        f"TOTAL TIME: "
        f"{total_duration:.2f}s"
    )

    if results:

        average = (
            total_duration
            / len(
                results
            )
        )

        print(
            f"AVERAGE TIME: "
            f"{average:.2f}s"
        )

    print(
        "=" * 72
    )

    # -----------------------------------------------------
    # Save machine-readable report
    # -----------------------------------------------------

    report_file = (
        BASE_DIR
        / "evaluation_report.json"
    )

    serializable_results = []

    for item in results:

        result_data = (
            item.get(
                "result",
                {}
            )
        )

        serializable_results.append(
            {
                "id":
                    item[
                        "id"
                    ],

                "query":
                    item[
                        "query"
                    ],

                "passed":
                    item[
                        "passed"
                    ],

                "duration":
                    round(
                        item[
                            "duration"
                        ],
                        3,
                    ),

                "failures":
                    item[
                        "failures"
                    ],

                "observed": {
                    "intent":
                        result_data.get(
                            "intent"
                        ),

                    "category":
                        result_data.get(
                            "category"
                        ),

                    "day":
                        result_data.get(
                            "day"
                        ),

                    "start_after":
                        result_data.get(
                            "start_after"
                        ),

                    "start_before":
                        result_data.get(
                            "start_before"
                        ),

                    "center_name":
                        result_data.get(
                            "center_name"
                        ),

                    "instructor":
                        result_data.get(
                            "instructor"
                        ),

                    "target_audience":
                        result_data.get(
                            "target_audience"
                        ),

                    "age":
                        result_data.get(
                            "age"
                        ),

                    "waiting_for_clarification":
                        result_data.get(
                            "waiting_for_clarification"
                        ),

                    "result_count":
                        _result_count(
                            result_data
                        ),
                },
            }
        )

    with report_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "summary": {
                    "passed":
                        passed,

                    "failed":
                        failed,

                    "total":
                        len(
                            results
                        ),

                    "score":
                        round(
                            percentage,
                            2,
                        ),

                    "total_duration":
                        round(
                            total_duration,
                            3,
                        ),
                },

                "results":
                    serializable_results,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        "Report saved to:"
    )

    print(
        report_file
    )


if __name__ == "__main__":
    main()
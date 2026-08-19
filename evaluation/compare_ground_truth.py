from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


GROUND_TRUTH_FILE = (
    PROJECT_ROOT
    / "data"
    / "ground_truth"
    / "לוח_שעות_וחוגים_נתוני_בדיקה.xlsx"
)

EXTRACTED_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "activities_from_lecturer.json"
)


def normalize_value(value: Any) -> Any:
    """
    Normalizes values before comparison.
    """

    if pd.isna(value):
        return None

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

    return value


def normalize_name(
    name: str | None,
) -> str | None:
    """
    Basic name corrections only for evaluation.

    We keep raw_name untouched in the extraction output.
    """

    if name is None:
        return None

    corrections = {
        "התעמלות מתונהה": "התעמלות מתונה",
        "פילטיס": "פילאטיס",
    }

    return corrections.get(
        name,
        name,
    )


def normalize_audience(
    value: str | None,
) -> str | None:
    """
    Normalizes audience labels across Hebrew and English.

    Examples:
    Women only -> נשים
    Mixed -> גם לגברים
    """

    if value is None:
        return None

    cleaned = str(value).strip()

    mapping = {
        "Women only": "נשים",
        "Women Only": "נשים",
        "women only": "נשים",
        "נשים": "נשים",

        "Mixed": "גם לגברים",
        "mixed": "גם לגברים",
        "גם לגברים": "גם לגברים",
    }

    return mapping.get(
        cleaned,
        cleaned,
    )


def normalize_location(
    location: str | None,
) -> str | None:
    """
    Normalizes spacing and dash characters in locations.
    """

    if location is None:
        return None

    cleaned = str(
        location
    ).strip()

    cleaned = cleaned.replace(
        "-",
        "–",
    )

    cleaned = " ".join(
        cleaned.split()
    )

    return cleaned or None


def build_actual_location(
    activity: dict[str, Any],
) -> str | None:
    """
    Reconstructs the lecturer-style location for evaluation.

    Our schema may store:
        location = אולם ספורט
        branch = א

    Ground Truth may store:
        אולם ספורט – סניף א'
    """

    location = normalize_location(
        activity.get("location")
    )

    branch = normalize_value(
        activity.get("branch")
    )

    if location is None:
        return None

    if branch:
        return normalize_location(
            f"{location} – סניף {branch}'"
        )

    return location


def locations_match(
    expected_location: str | None,
    actual_activity: dict[str, Any],
) -> bool:
    """
    Compares Ground Truth location with our structured
    location + branch representation.
    """

    expected = normalize_location(
        expected_location
    )

    actual_combined = (
        build_actual_location(
            actual_activity
        )
    )

    if expected == actual_combined:
        return True

    actual_plain = normalize_location(
        actual_activity.get(
            "location"
        )
    )

    if expected == actual_plain:
        return True

    return False


def load_ground_truth(
) -> list[dict[str, Any]]:
    """
    Loads lecturer Ground Truth from the schedule sheet.
    """

    df = pd.read_excel(
        GROUND_TRUTH_FILE,
        sheet_name="לוח_שעות",
    )

    records: list[
        dict[str, Any]
    ] = []

    for _, row in df.iterrows():
        records.append(
            {
                "source_file": normalize_value(
                    row.get(
                        "קובץ_מקור"
                    )
                ),

                "center_name": normalize_value(
                    row.get(
                        "שם_המרכז"
                    )
                ),

                "day": normalize_value(
                    row.get(
                        "יום"
                    )
                ),

                "start_time": normalize_value(
                    row.get(
                        "שעת_התחלה"
                    )
                ),

                "end_time": normalize_value(
                    row.get(
                        "שעת_סיום"
                    )
                ),

                "name": normalize_value(
                    row.get(
                        "שם_החוג"
                    )
                ),

                "raw_name": normalize_value(
                    row.get(
                        "שם_בקובץ"
                    )
                ),

                "english_name": normalize_value(
                    row.get(
                        "שם_באנגלית"
                    )
                ),

                "instructor": normalize_value(
                    row.get(
                        "מדריך"
                    )
                ),

                "location": normalize_value(
                    row.get(
                        "אולם"
                    )
                ),

                "target_audience": normalize_value(
                    row.get(
                        "קהל_יעד"
                    )
                ),

                "notes": normalize_value(
                    row.get(
                        "הערות"
                    )
                ),

                "trap": normalize_value(
                    row.get(
                        "מלכודת_בדיקה"
                    )
                ),
            }
        )

    return records


def load_extracted(
) -> list[dict[str, Any]]:
    """
    Loads our unified extraction result.
    """

    with open(
        EXTRACTED_FILE,
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def logical_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    Main identity of a class.

    We intentionally do NOT include instructor/location
    because those may be missing or dirty.
    """

    return (
        activity.get(
            "source_file"
        ),

        activity.get(
            "day"
        ),

        activity.get(
            "start_time"
        ),

        normalize_name(
            activity.get(
                "name"
            )
        ),
    )


def deduplicate_ground_truth(
    records: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    Removes intentional duplicate rows from Ground Truth.
    """

    seen: set[
        tuple[Any, ...]
    ] = set()

    unique: list[
        dict[str, Any]
    ] = []

    for record in records:
        key = logical_key(
            record
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            record
        )

    return unique


def index_by_key(
    records: list[
        dict[str, Any]
    ],
) -> dict[
    tuple[Any, ...],
    dict[str, Any],
]:
    return {
        logical_key(record): record
        for record in records
    }


def compare_fields(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> dict[
    str,
    tuple[Any, Any],
]:
    """
    Returns field mismatches for one matched activity.
    """

    mismatches: dict[
        str,
        tuple[Any, Any],
    ] = {}

    # Simple fields that can be compared directly.
    simple_fields = [
        "end_time",
        "instructor",
    ]

    for field in simple_fields:
        expected_value = (
            expected.get(field)
        )

        actual_value = (
            actual.get(field)
        )

        if (
            expected_value
            != actual_value
        ):
            mismatches[field] = (
                expected_value,
                actual_value,
            )

    # Compare audience semantically rather than by language.
    expected_audience = (
        normalize_audience(
            expected.get(
                "target_audience"
            )
        )
    )

    actual_audience = (
        normalize_audience(
            actual.get(
                "target_audience"
            )
        )
    )

    if (
        expected_audience
        != actual_audience
    ):
        mismatches[
            "target_audience"
        ] = (
            expected.get(
                "target_audience"
            ),
            actual.get(
                "target_audience"
            ),
        )

    # Compare location while respecting structured branch.
    if not locations_match(
        expected.get(
            "location"
        ),
        actual,
    ):
        mismatches[
            "location"
        ] = (
            expected.get(
                "location"
            ),
            build_actual_location(
                actual
            ),
        )

    return mismatches


def print_mismatch_summary(
    field_mismatches: list[
        dict[str, Any]
    ],
) -> None:
    """
    Prints mismatch counts grouped by source file and field.
    """

    summary: dict[
        str,
        dict[str, int],
    ] = {}

    for item in field_mismatches:
        key = item[
            "key"
        ]

        source_file = key[0]

        if (
            source_file
            not in summary
        ):
            summary[
                source_file
            ] = {}

        for field in item[
            "mismatches"
        ]:
            summary[
                source_file
            ][field] = (
                summary[
                    source_file
                ].get(
                    field,
                    0,
                )
                + 1
            )

    print(
        "\n=== Field Mismatch Summary ==="
    )

    total_by_field: dict[
        str,
        int,
    ] = {}

    for source_file in sorted(
        summary
    ):
        print(
            "\n"
            + source_file
        )

        for field, count in sorted(
            summary[
                source_file
            ].items()
        ):
            print(
                f"- {field}: {count}"
            )

            total_by_field[
                field
            ] = (
                total_by_field.get(
                    field,
                    0,
                )
                + count
            )

    print(
        "\n=== Total Mismatches By Field ==="
    )

    if not total_by_field:
        print(
            "- none"
        )

    for field, count in sorted(
        total_by_field.items()
    ):
        print(
            f"- {field}: {count}"
        )


def main() -> None:
    if (
        sys.platform
        == "win32"
    ):
        try:
            sys.stdout.reconfigure(
                encoding="utf-8"
            )

        except (
            AttributeError,
            OSError,
        ):
            pass

    ground_truth_raw = (
        load_ground_truth()
    )

    ground_truth = (
        deduplicate_ground_truth(
            ground_truth_raw
        )
    )

    extracted = (
        load_extracted()
    )

    expected_index = (
        index_by_key(
            ground_truth
        )
    )

    actual_index = (
        index_by_key(
            extracted
        )
    )

    expected_keys = set(
        expected_index.keys()
    )

    actual_keys = set(
        actual_index.keys()
    )

    matched_keys = (
        expected_keys
        & actual_keys
    )

    missing_keys = (
        expected_keys
        - actual_keys
    )

    extra_keys = (
        actual_keys
        - expected_keys
    )

    field_mismatches: list[
        dict[str, Any]
    ] = []

    for key in sorted(
        matched_keys,
        key=str,
    ):
        expected = (
            expected_index[
                key
            ]
        )

        actual = (
            actual_index[
                key
            ]
        )

        mismatches = (
            compare_fields(
                expected,
                actual,
            )
        )

        if mismatches:
            field_mismatches.append(
                {
                    "key": key,
                    "mismatches": mismatches,
                }
            )

    total_expected = len(
        expected_keys
    )

    total_matched = len(
        matched_keys
    )

    recall = (
        total_matched
        / total_expected
        if total_expected
        else 0
    )

    precision = (
        total_matched
        / len(actual_keys)
        if actual_keys
        else 0
    )

    print(
        "\n=== Ground Truth Evaluation ==="
    )

    print(
        "\nRaw Ground Truth rows:",
        len(
            ground_truth_raw
        ),
    )

    print(
        "Logical Ground Truth after dedup:",
        len(
            ground_truth
        ),
    )

    print(
        "Extracted rows:",
        len(
            extracted
        ),
    )

    print(
        "\nMatched:",
        total_matched,
    )

    print(
        "Missing:",
        len(
            missing_keys
        ),
    )

    print(
        "Extra:",
        len(
            extra_keys
        ),
    )

    print(
        f"Recall: {recall:.2%}"
    )

    print(
        f"Precision: {precision:.2%}"
    )

    if missing_keys:
        print(
            "\n=== Missing activities ==="
        )

        for key in sorted(
            missing_keys,
            key=str,
        ):
            print(
                "-",
                key,
            )

    if extra_keys:
        print(
            "\n=== Extra activities ==="
        )

        for key in sorted(
            extra_keys,
            key=str,
        ):
            print(
                "-",
                key,
            )

    print(
        "\nField mismatch records:",
        len(
            field_mismatches
        ),
    )

    print_mismatch_summary(
        field_mismatches
    )

    print(
        "\n=== First 20 Detailed Mismatches ==="
    )

    for item in field_mismatches[
        :20
    ]:
        print(
            "\nActivity:",
            item["key"],
        )

        for field, values in item[
            "mismatches"
        ].items():

            (
                expected_value,
                actual_value,
            ) = values

            print(
                f"  {field}:"
            )

            print(
                "    expected:",
                expected_value,
            )

            print(
                "    actual:  ",
                actual_value,
            )


if __name__ == "__main__":
    main()
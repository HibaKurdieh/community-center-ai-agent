from __future__ import annotations

from pathlib import Path

from ingestion.universal_docx_parser import (
    parse_with_known_parsers,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "lecturer_samples"
)


TEST_CASES = [
    (
        "01_מרכז_ספורט_הדס_בסיסי.docx",
        "basic",
        15,
    ),
    (
        "02_מרכז_ספורט_אלונים_טבלה.docx",
        "table",
        15,
    ),
    (
        "03_מרכז_כושר_נופים_מלוכלך.docx",
        "dirty",
        13,
    ),
    (
        "04_Neve_Sport_Center_bilingual.docx",
        "bilingual",
        12,
    ),
    (
        "05_מרכז_ספורט_מעיין_לפי_חוג.docx",
        "grouped",
        14,
    ),
    (
        "06_מרכז_ספורט_גלים_מקרי_קצה.docx",
        "edge_case",
        16,
    ),
]


def main() -> None:
    passed = 0

    print(
        "\n"
        "=== Universal DOCX Parser Test ==="
        "\n"
    )

    for (
        filename,
        expected_parser,
        expected_count,
    ) in TEST_CASES:

        file_path = (
            DATA_DIR
            / filename
        )

        (
            activities,
            selected_parser,
            attempts,
        ) = parse_with_known_parsers(
            file_path
        )

        parser_ok = (
            selected_parser
            == expected_parser
        )

        count_ok = (
            len(activities)
            == expected_count
        )

        success = (
            parser_ok
            and count_ok
        )

        if success:
            passed += 1

        print(
            filename
        )

        print(
            "Expected parser:",
            expected_parser,
        )

        print(
            "Selected parser:",
            selected_parser,
        )

        print(
            "Expected activities:",
            expected_count,
        )

        print(
            "Extracted activities:",
            len(activities),
        )

        print(
            "\nAttempts:"
        )

        for attempt in attempts:
            print(
                f"  {attempt.parser_name:12}"
                f" score={attempt.score:.3f}"
                f" valid={attempt.valid_count}"
                f" total={attempt.total_count}"
            )

            if attempt.error:
                print(
                    "    error:",
                    attempt.error,
                )

        print(
            "\n",
            "PASS ✅"
            if success
            else "FAIL ❌",
        )

        print(
            "-" * 72
        )

    total = len(
        TEST_CASES
    )

    print(
        f"\nFINAL RESULT: "
        f"{passed}/{total} passed"
    )


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
from pathlib import Path

from database.activities_repository import (
    insert_new_activities,
)
from ingestion.universal_docx_parser import (
    parse_universal_docx,
    print_attempts,
)


def ingest_docx(
    file_path: Path,
    *,
    save_to_database: bool = False,
) -> list[dict]:
    """
    Universal DOCX ingestion pipeline.

    Flow:
        DOCX
        -> known deterministic parsers
        -> generic LLM fallback if needed
        -> normalized Activity records
        -> Supabase (when save_to_database=True)

    No JSON file is created.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            file_path
        )

    if file_path.suffix.lower() != ".docx":
        raise ValueError(
            "Currently universal ingestion supports DOCX files only."
        )

    print(
        "\n=== Universal Ingestion ==="
    )

    print(
        "File:",
        file_path.name,
    )

    (
        activities,
        parser_name,
        attempts,
    ) = parse_universal_docx(
        file_path
    )

    print_attempts(
        attempts
    )

    print(
        "\nSelected parser:",
        parser_name,
    )

    print(
        "Extracted activities:",
        len(activities),
    )

    if not activities:
        print(
            "\nNo valid activities were extracted."
        )

        return []

    # --------------------------------------------------
    # Dry run
    # --------------------------------------------------

    if not save_to_database:
        print(
            "\nDRY RUN:"
            " Nothing was written to Supabase."
        )

        return activities

    # --------------------------------------------------
    # Save directly to Supabase
    # --------------------------------------------------

    print(
        "\nSaving activities to Supabase..."
    )

    stats = insert_new_activities(
        activities
    )

    print(
        "\n=== Supabase Result ==="
    )

    print(
        "Received:",
        stats["received"],
    )

    print(
        "Inserted:",
        stats["inserted"],
    )

    print(
        "Duplicates:",
        stats["duplicates"],
    )

    return activities


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Universal DOCX ingestion "
            "for community-center activities."
        )
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to the DOCX file.",
    )

    parser.add_argument(
        "--save",
        action="store_true",
        help=(
            "Save new activities directly "
            "to Supabase."
        ),
    )

    args = parser.parse_args()

    ingest_docx(
        args.file,
        save_to_database=args.save,
    )


if __name__ == "__main__":
    main()
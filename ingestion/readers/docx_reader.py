from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from docx import Document


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LECTURER_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "lecturer_samples"
)


def read_docx(file_path: Path) -> dict[str, Any]:
    """
    קורא קובץ Word ומחזיר את הטקסט והטבלאות
    בלי לבצע עדיין parsing או normalization.
    """

    document = Document(file_path)

    paragraphs: list[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            paragraphs.append(text)

    tables: list[list[list[str]]] = []

    for table in document.tables:
        table_rows: list[list[str]] = []

        for row in table.rows:
            cells = [
                cell.text.strip()
                for cell in row.cells
            ]

            table_rows.append(cells)

        tables.append(table_rows)

    return {
        "source_file": file_path.name,
        "paragraphs": paragraphs,
        "tables": tables,
    }


def find_docx_files() -> list[Path]:
    """
    מחזיר את כל קבצי ה-DOCX של המרצה.
    """

    if not LECTURER_DATA_DIR.exists():
        raise FileNotFoundError(
            f"לא נמצאה תיקיית הנתונים: {LECTURER_DATA_DIR}"
        )

    return sorted(
        LECTURER_DATA_DIR.glob("*.docx")
    )


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    files = find_docx_files()

    print("\n=== Lecturer DOCX Reader ===")
    print(f"נמצאו {len(files)} קבצי Word.\n")

    for file_path in files:
        data = read_docx(file_path)

        print("—" * 60)
        print("קובץ:", data["source_file"])
        print("מספר פסקאות:", len(data["paragraphs"]))
        print("מספר טבלאות:", len(data["tables"]))

        print("\nדוגמת טקסט:")

        for paragraph in data["paragraphs"][:5]:
            print("-", paragraph)

        if data["tables"]:
            print("\nדוגמה מהטבלה הראשונה:")

            first_table = data["tables"][0]

            for row in first_table[:3]:
                print(row)

        print()


if __name__ == "__main__":
    main()
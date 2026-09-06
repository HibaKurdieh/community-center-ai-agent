from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv

from database.supabase_client import (
    get_supabase_client,
)
from ingestion.readers.excel_reader import (
    SUPPORTED_EXCEL_SUFFIXES,
)


load_dotenv()


SUPPORTED_SOURCE_SUFFIXES = {
    ".docx",
    *SUPPORTED_EXCEL_SUFFIXES,
}


# ---------------------------------------------------------
# הגדרת מקור הקבצים
# ---------------------------------------------------------

"""
קוראת את שם מאגר הקבצים ממשתני הסביבה
ומוודאת שהערך קיים לפני ניסיון הגישה לאחסון
"""
def _get_source_bucket() -> str:
    bucket_name = os.getenv(
        "SOURCE_BUCKET"
    )

    if not bucket_name:
        raise RuntimeError(
            "SOURCE_BUCKET לא נמצא "
            "יש לבדוק את קובץ .env"
        )

    return bucket_name


# ---------------------------------------------------------
# איתור קבצים באחסון
# ---------------------------------------------------------

"""
מחזירה את שמות כל קובצי המקור הנתמכים
שקיימים במאגר הקבצים של המערכת
"""
def list_source_files() -> list[str]:
    client = (
        get_supabase_client()
    )

    bucket_name = (
        _get_source_bucket()
    )

    items = (
        client.storage
        .from_(
            bucket_name
        )
        .list()
    )

    file_names: list[str] = []

    for item in items:
        name = item.get(
            "name"
        )

        if not name:
            continue

        suffix = (
            Path(name)
            .suffix
            .lower()
        )

        if (
            suffix
            not in SUPPORTED_SOURCE_SUFFIXES
        ):
            continue

        file_names.append(
            name
        )

    return sorted(
        file_names
    )


# ---------------------------------------------------------
# הורדת הקבצים
# ---------------------------------------------------------

"""
מורידה את כל קובצי המקור הנתמכים
לתיקייה זמנית לצורך תהליך הקליטה

התיקייה הזמנית נמחקת אוטומטית
לאחר סיום העבודה עם הקבצים
"""
@contextmanager
def downloaded_source_files() -> Iterator[
    list[Path]
]:
    client = (
        get_supabase_client()
    )

    bucket_name = (
        _get_source_bucket()
    )

    file_names = (
        list_source_files()
    )

    with tempfile.TemporaryDirectory(
        prefix="community_center_sources_"
    ) as temporary_directory:

        temporary_path = Path(
            temporary_directory
        )

        downloaded_files: list[
            Path
        ] = []

        for file_name in file_names:

            file_bytes = (
                client.storage
                .from_(
                    bucket_name
                )
                .download(
                    file_name
                )
            )

            local_path = (
                temporary_path
                / Path(
                    file_name
                ).name
            )

            local_path.write_bytes(
                file_bytes
            )

            downloaded_files.append(
                local_path
            )

        yield downloaded_files


# ---------------------------------------------------------
# בדיקה ידנית
# ---------------------------------------------------------

if __name__ == "__main__":

    print(
        "קובצי המקור שנמצאו:"
    )

    file_names = (
        list_source_files()
    )

    for file_name in file_names:
        print(
            "-",
            file_name,
        )

    with downloaded_source_files() as files:

        print(
            "\nקבצים שהורדו זמנית:"
        )

        for file_path in files:
            print(
                "-",
                file_path.name,
                file_path.stat().st_size,
                "bytes",
            )
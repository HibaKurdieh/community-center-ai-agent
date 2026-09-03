"""
הקובץ קורא קובצי גיליון
וממיר את שורות הפעילויות למבנה הפעילות האחיד

אם קיימת לשונית בשם הפעילויות
המערכת משתמשת בה כברירת מחדל

אם היא אינה קיימת
המערכת משתמשת בלשונית הראשונה
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ingestion.source_adapter import (
    adapt_activity_record,
)


SUPPORTED_EXCEL_SUFFIXES = {
    ".xlsx",
    ".xlsm",
}


def _dataframe_to_records(
    dataframe: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    ממירה את טבלת הגיליון
    לרשימת רשומות ומנקה ערכים חסרים
    """

    cleaned = dataframe.where(
        pd.notna(
            dataframe
        ),
        None,
    )

    return cleaned.to_dict(
        orient="records"
    )


def read_excel_activities(
    file_path: str | Path,
    *,
    sheet_name: str | None = None,
    default_center_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    קוראת פעילויות מקובץ גיליון
    ומחזירה אותן במבנה האחיד של המערכת
    """

    path = Path(
        file_path
    )

    if not path.exists():
        raise FileNotFoundError(
            path
        )

    if (
        path.suffix.lower()
        not in SUPPORTED_EXCEL_SUFFIXES
    ):
        raise ValueError(
            f"סוג קובץ הגיליון אינו נתמך "
            f"{path.suffix}"
        )

    workbook = pd.read_excel(
        path,
        sheet_name=None,
        engine="openpyxl",
    )

    if not workbook:
        return []

    if sheet_name is not None:

        if sheet_name not in workbook:
            raise ValueError(
                f"הלשונית לא נמצאה "
                f"{sheet_name}"
            )

        selected_sheet = (
            sheet_name
        )

    elif "activities" in workbook:

        selected_sheet = (
            "activities"
        )

    else:
        selected_sheet = next(
            iter(
                workbook
            )
        )

    dataframe = workbook[
        selected_sheet
    ]

    records = _dataframe_to_records(
        dataframe
    )

    activities: list[
        dict[str, Any]
    ] = []

    for record in records:

        if not any(
            value is not None
            and str(value).strip()
            for value in record.values()
        ):
            continue

        activity = (
            adapt_activity_record(
                record,
                source_name=path.name,
                default_center_name=(
                    default_center_name
                ),
            )
        )

        activities.append(
            activity
        )

    return activities
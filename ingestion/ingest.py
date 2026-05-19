"""Ingestion: קורא את קובץ ה-Excel ומייצר JSON תחת data/processed/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_XLSX = PROJECT_ROOT / "data" / "raw" / "community_center_data.xlsx"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def _ensure_utf8_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """מנרמל ערכי זמן/תאריך למחרוזות ISO ליציבות ב-JSON."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S")
        elif out[col].dtype == object:
            out[col] = out[col].apply(
                lambda x: x.strftime("%H:%M:%S")
                if hasattr(x, "strftime") and not isinstance(x, str)
                else x
            )
    return out.to_dict(orient="records")


def run() -> None:
    _ensure_utf8_stdout()
    if not RAW_XLSX.is_file():
        raise FileNotFoundError(f"לא נמצא קובץ Excel: {RAW_XLSX}")

    activities_df = pd.read_excel(RAW_XLSX, sheet_name="activities")
    events_df = pd.read_excel(RAW_XLSX, sheet_name="events")
    volunteer_df = pd.read_excel(RAW_XLSX, sheet_name="volunteer_opportunities")

    print("\n=== סיכום נתונים ===")
    print(f"חוגים: {len(activities_df)}")
    print(f"אירועים: {len(events_df)}")
    print(f"התנדבות: {len(volunteer_df)}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    payloads = {
        "activities.json": _df_to_records(activities_df),
        "events.json": _df_to_records(events_df),
        "volunteer_opportunities.json": _df_to_records(volunteer_df),
    }

    for filename, data in payloads.items():
        path = PROCESSED_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nנשמרו קבצי JSON תחת: {PROCESSED_DIR}")


if __name__ == "__main__":
    run()

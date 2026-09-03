"""
הקובץ מכין שכבת קריאה כללית
עבור מקור נתונים חיצוני שמחזיר מידע במבנה גייסון

הקובץ מקבל את תגובת המקור
מחלץ ממנה רשומות של פעילויות
ומעביר כל רשומה לשכבת ההתאמה האחידה

כאשר יהיה מקור חיצוני אמיתי
יהיה ניתן להתאים רק את שכבת החיבור
בלי לשנות את שאר תהליך קליטת הנתונים
"""

from __future__ import annotations

import json
from typing import Any
from urllib.request import (
    Request,
    urlopen,
)

from ingestion.source_adapter import (
    adapt_activity_record,
)


POSSIBLE_RECORD_KEYS = (
    "activities",
    "data",
    "results",
    "items",
)


def _extract_records(
    payload: Any,
) -> list[dict[str, Any]]:
    """
    מחלצת רשימת פעילויות
    מתוך מבנים נפוצים של מידע חיצוני
    """

    if isinstance(
        payload,
        list,
    ):
        return [
            item
            for item in payload
            if isinstance(
                item,
                dict,
            )
        ]

    if isinstance(
        payload,
        dict,
    ):

        for key in (
            POSSIBLE_RECORD_KEYS
        ):

            value = payload.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return [
                    item
                    for item in value
                    if isinstance(
                        item,
                        dict,
                    )
                ]

    raise ValueError(
        "לא נמצאה רשימת פעילויות "
        "בתגובת המקור החיצוני"
    )


def fetch_external_json(
    api_url: str,
    *,
    api_key: str | None = None,
    timeout: int = 30,
) -> Any:
    """
    שולחת בקשת קריאה למקור החיצוני
    ומחזירה את המידע שהתקבל

    אם קיים מפתח גישה
    הוא נשלח כחלק מפרטי הבקשה
    """

    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "community-center-ai-agent"
        ),
    }

    if api_key:
        headers[
            "Authorization"
        ] = (
            f"Bearer {api_key}"
        )

    request = Request(
        api_url,
        headers=headers,
        method="GET",
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:

        raw_data = response.read()

    return json.loads(
        raw_data.decode(
            "utf-8"
        )
    )


def read_external_activities(
    api_url: str,
    *,
    api_key: str | None = None,
    source_name: str = "external_api",
    default_center_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    קוראת פעילויות ממקור נתונים חיצוני
    וממירה אותן למבנה הפעילות האחיד של המערכת
    """

    payload = fetch_external_json(
        api_url,
        api_key=api_key,
    )

    records = _extract_records(
        payload
    )

    return [
        adapt_activity_record(
            record,
            source_name=source_name,
            default_center_name=(
                default_center_name
            ),
        )
        for record in records
    ]
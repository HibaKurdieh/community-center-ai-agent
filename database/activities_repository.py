from __future__ import annotations

from typing import Any

from database.supabase_client import (
    get_supabase_client,
)


TABLE_NAME = "activities"


# Fields that exist in the Supabase table.
ACTIVITY_FIELDS = (
    "source_file",
    "center_name",
    "branch",
    "day",
    "raw_day",
    "start_time",
    "end_time",
    "end_time_source",
    "raw_time",
    "name",
    "raw_name",
    "english_name",
    "instructor",
    "location",
    "target_audience",
    "min_age",
    "max_age",
    "capacity",
    "level",
    "notes",
    "season",
    "valid_from",
    "source_language",
    "status",
)


# These fields are NOT NULL in Supabase.
REQUIRED_FIELDS = (
    "source_file",
    "center_name",
    "day",
    "raw_day",
    "start_time",
    "name",
    "raw_name",
    "target_audience",
    "source_language",
    "status",
)


def _has_value(
    value: Any,
) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _activity_key(
    activity: dict[str, Any],
) -> tuple[Any, ...]:
    """
    Logical key used to detect duplicate activities.

    source_file is intentionally NOT part of the key,
    so the same activity coming from another source
    is not inserted twice.
    """

    return (
        activity.get("center_name"),
        activity.get("day"),
        activity.get("start_time"),
        activity.get("end_time"),
        activity.get("name"),
        activity.get("instructor"),
        activity.get("location"),
    )


def _validate_activity(
    activity: dict[str, Any],
) -> None:
    """
    Validates fields that must exist before inserting
    an activity into Supabase.
    """

    missing = [
        field
        for field in REQUIRED_FIELDS
        if not _has_value(
            activity.get(field)
        )
    ]

    if missing:
        raise ValueError(
            "Activity is missing required fields: "
            + ", ".join(missing)
        )


def _prepare_activity(
    activity: dict[str, Any],
) -> dict[str, Any]:
    """
    Keeps only fields that belong to the database table.

    This prevents accidental extra fields from being
    sent to Supabase.
    """

    _validate_activity(activity)

    return {
        field: activity.get(field)
        for field in ACTIVITY_FIELDS
    }


def get_existing_activity_keys(
    client=None,
) -> set[tuple[Any, ...]]:
    """
    Reads the current activities from Supabase and
    builds duplicate-detection keys.
    """

    if client is None:
        client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select(
            "center_name,"
            "day,"
            "start_time,"
            "end_time,"
            "name,"
            "instructor,"
            "location"
        )
        .execute()
    )

    existing = response.data or []

    return {
        _activity_key(activity)
        for activity in existing
    }


def insert_new_activities(
    activities: list[dict[str, Any]],
) -> dict[str, int]:
    """
    Inserts only activities that do not already exist.

    Returns statistics:
    {
        "received": ...,
        "inserted": ...,
        "duplicates": ...
    }
    """

    if not activities:
        return {
            "received": 0,
            "inserted": 0,
            "duplicates": 0,
        }

    client = get_supabase_client()

    existing_keys = (
        get_existing_activity_keys(
            client
        )
    )

    new_records: list[
        dict[str, Any]
    ] = []

    seen_in_batch: set[
        tuple[Any, ...]
    ] = set()

    duplicates = 0

    for activity in activities:
        prepared = _prepare_activity(
            activity
        )

        key = _activity_key(
            prepared
        )

        if (
            key in existing_keys
            or key in seen_in_batch
        ):
            duplicates += 1
            continue

        seen_in_batch.add(key)

        new_records.append(
            prepared
        )

    if not new_records:
        return {
            "received": len(activities),
            "inserted": 0,
            "duplicates": duplicates,
        }

    response = (
        client.table(TABLE_NAME)
        .insert(new_records)
        .execute()
    )

    inserted = len(
        response.data or []
    )

    return {
        "received": len(activities),
        "inserted": inserted,
        "duplicates": duplicates,
    }
def get_all_activities() -> list[dict[str, Any]]:
    """
    Reads all activities from Supabase.
    """

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .order("id")
        .execute()
    )

    return response.data or []
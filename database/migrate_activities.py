import json
from pathlib import Path

from database.supabase_client import get_supabase_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ACTIVITIES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "activities_from_lecturer.json"
)

TABLE_NAME = "activities"


def load_activities() -> list[dict]:
    with ACTIVITIES_FILE.open("r", encoding="utf-8") as file:
        activities = json.load(file)

    if not isinstance(activities, list):
        raise ValueError("Activities JSON must contain a list.")

    print(f"Loaded {len(activities)} activities from JSON.")

    return activities


def check_table_is_empty(client) -> None:
    response = (
        client.table(TABLE_NAME)
        .select("id")
        .limit(1)
        .execute()
    )

    if response.data:
        raise RuntimeError(
            "Supabase activities table is not empty. "
            "Migration stopped to prevent duplicate records."
        )


def migrate_activities() -> None:
    activities = load_activities()

    if len(activities) != 85:
        raise RuntimeError(
            f"Expected 85 activities, found {len(activities)}. "
            "Migration stopped."
        )

    client = get_supabase_client()

    print("Connected to Supabase.")

    check_table_is_empty(client)

    print("Supabase activities table is empty.")

    response = (
        client.table(TABLE_NAME)
        .insert(activities)
        .execute()
    )

    inserted = len(response.data or [])

    print(f"Inserted {inserted} activities into Supabase.")

    verification = (
        client.table(TABLE_NAME)
        .select("id")
        .execute()
    )

    total_in_database = len(verification.data or [])

    print(f"Activities currently in Supabase: {total_in_database}")

    if total_in_database != len(activities):
        raise RuntimeError(
            "Migration verification failed: "
            f"JSON={len(activities)}, Supabase={total_in_database}"
        )

    print("Migration completed successfully ✅")


if __name__ == "__main__":
    migrate_activities()
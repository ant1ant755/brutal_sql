"""Save a schema snapshot to a uniquely named, timestamped JSON file."""

import re
from datetime import UTC, datetime
from pathlib import Path

from brutal_sql.db.schema_model import PostgresSchemaObject

UNSAFE_FILE_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]")


def save_schema_snapshot(
    schema_object: PostgresSchemaObject, staging_folder: Path
) -> Path:
    """Write the snapshot to a new timestamped JSON file and return its path.

    Creates the staging folder if needed. Never overwrites an existing file:
    raises ``FileExistsError`` on a name clash.
    """
    staging_folder = Path(staging_folder)
    staging_folder.mkdir(parents=True, exist_ok=True)
    file_name = build_snapshot_file_name(schema_object.schema_name, datetime.now(UTC))
    file_path = staging_folder / file_name
    with file_path.open("x", encoding="utf-8") as snapshot_file:
        snapshot_file.write(schema_object.to_json())
    return file_path.resolve()


def build_snapshot_file_name(schema_name: str, saved_at: datetime) -> str:
    """Return ``<schema>_<UTC timestamp to the microsecond>.json`` for a snapshot.

    Characters that are unsafe in file names are replaced with ``_``.
    Raises ``ValueError`` if ``saved_at`` has no time zone.
    """
    if saved_at.tzinfo is None:
        raise ValueError("saved_at must be time-zone aware")
    safe_schema_name = UNSAFE_FILE_NAME_CHARACTERS.sub("_", schema_name) or "schema"
    timestamp = saved_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{safe_schema_name}_{timestamp}.json"

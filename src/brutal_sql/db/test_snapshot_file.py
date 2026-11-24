"""Unit tests for saving schema snapshots to timestamped files. No database needed."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from brutal_sql.db import snapshot_file
from brutal_sql.db.schema_model import EnumDetails, PostgresSchemaObject
from brutal_sql.db.snapshot_file import build_snapshot_file_name, save_schema_snapshot

SAVED_AT = datetime(2026, 11, 24, 10, 30, 15, 123456, tzinfo=UTC)


@pytest.fixture
def small_snapshot() -> PostgresSchemaObject:
    """A snapshot with no tables and one enum, for save tests."""
    return PostgresSchemaObject(
        "test", "shop", SAVED_AT.isoformat(), [], [EnumDetails("mood", ["ok"])]
    )


# build_snapshot_file_name


def test_file_name_has_schema_and_utc_timestamp() -> None:
    file_name = build_snapshot_file_name("shop", SAVED_AT)
    assert file_name == "shop_20261124T103015123456Z.json"


def test_file_name_converts_to_utc() -> None:
    singapore_time = SAVED_AT.astimezone(timezone(timedelta(hours=8)))
    assert build_snapshot_file_name("shop", singapore_time) == (
        "shop_20261124T103015123456Z.json"
    )


def test_file_name_replaces_unsafe_characters() -> None:
    file_name = build_snapshot_file_name("../my schema", SAVED_AT)
    assert file_name == "___my_schema_20261124T103015123456Z.json"
    assert "/" not in file_name


def test_file_name_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="time-zone aware"):
        build_snapshot_file_name("shop", datetime(2026, 11, 24))


# save_schema_snapshot


def test_save_writes_loadable_json_in_staging_folder(
    small_snapshot: PostgresSchemaObject, tmp_path: Path
) -> None:
    file_path = save_schema_snapshot(small_snapshot, tmp_path)
    assert file_path.parent == tmp_path.resolve()
    assert file_path.name.startswith("shop_") and file_path.suffix == ".json"
    assert PostgresSchemaObject.load_from_file(file_path) == small_snapshot


def test_save_creates_missing_staging_folder(
    small_snapshot: PostgresSchemaObject, tmp_path: Path
) -> None:
    staging_folder = tmp_path / "staging" / "nested"
    file_path = save_schema_snapshot(small_snapshot, staging_folder)
    assert file_path.is_file()


def test_two_saves_give_two_files(
    small_snapshot: PostgresSchemaObject, tmp_path: Path
) -> None:
    first = save_schema_snapshot(small_snapshot, tmp_path)
    second = save_schema_snapshot(small_snapshot, tmp_path)
    assert first != second
    assert len(list(tmp_path.iterdir())) == 2


def test_save_rejects_staging_path_that_is_a_file(
    small_snapshot: PostgresSchemaObject, tmp_path: Path
) -> None:
    not_a_folder = tmp_path / "file.txt"
    not_a_folder.write_text("x")
    with pytest.raises(FileExistsError):
        save_schema_snapshot(small_snapshot, not_a_folder)


def test_save_never_overwrites_existing_file(
    small_snapshot: PostgresSchemaObject,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        snapshot_file, "build_snapshot_file_name", lambda *_: "clash.json"
    )
    (tmp_path / "clash.json").write_text("original")
    with pytest.raises(FileExistsError):
        save_schema_snapshot(small_snapshot, tmp_path)
    assert (tmp_path / "clash.json").read_text() == "original"

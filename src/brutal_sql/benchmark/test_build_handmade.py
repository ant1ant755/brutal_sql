"""Unit tests for the hand-made benchmark build script helpers."""

from pathlib import Path

import pytest

from brutal_sql.benchmark.build_handmade import (
    settings_from_environment,
    write_benchmark,
)
from brutal_sql.benchmark.loader import load_benchmark
from brutal_sql.benchmark.test_expected_rows import make_record
from brutal_sql.errors import ProcessingError

ENVIRONMENT = {
    "POSTGRES_DB": "bench_db",
    "POSTGRES_USER": "user-secret-value",
    "POSTGRES_PASSWORD": "password-secret-value",
}


def test_settings_from_environment_reads_postgres_keys() -> None:
    settings = settings_from_environment(ENVIRONMENT | {"POSTGRES_PORT": "5544"})
    assert settings.database == "bench_db"
    assert settings.port == 5544
    assert settings.host == "127.0.0.1"


def test_settings_from_environment_names_missing_keys_only() -> None:
    environment = {"POSTGRES_USER": "user-secret-value", "POSTGRES_DB": ""}
    with pytest.raises(ProcessingError) as raised:
        settings_from_environment(environment)
    message = str(raised.value)
    assert "POSTGRES_DB" in message and "POSTGRES_PASSWORD" in message
    assert (
        "user-secret-value" not in message
    ), "error message must not echo a credential"


def test_write_benchmark_round_trips_through_loader(tmp_path: Path) -> None:
    records = [make_record("A"), make_record("B")]
    path = tmp_path / "out.jsonl"
    write_benchmark(path, records)
    assert load_benchmark(path) == records


def test_write_benchmark_into_missing_folder_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_benchmark(tmp_path / "absent" / "out.jsonl", [make_record("A")])

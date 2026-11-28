"""Unit tests for the hand-made question set files (no database needed)."""

import pytest

from brutal_sql.benchmark.format import BenchmarkFormatError
from brutal_sql.benchmark.handmade import (
    HANDMADE_DIRECTORY,
    SCHEMA_PREFIX,
    handmade_schema_names,
    load_handmade_benchmark,
    read_schema_annotations,
    read_schema_script,
)

EXPECTED_SCHEMAS = ["school", "shop", "signup", "staff", "weather"]
# Patterns the ticket asks the set to cover (B.05 numbering).
REQUIRED_PATTERNS = {1, 2, 3, 7, 8, 9, 10, 11, 13, 15, 16}


def test_handmade_schema_names_lists_every_script() -> None:
    assert handmade_schema_names() == EXPECTED_SCHEMAS


def test_every_schema_script_recreates_its_own_schema() -> None:
    for name in handmade_schema_names():
        script = read_schema_script(name)
        assert f"DROP SCHEMA IF EXISTS {SCHEMA_PREFIX}{name} CASCADE" in script
        assert "REFERENCES" in script, f"{name} declares no foreign key"


def test_every_schema_has_annotations_for_itself() -> None:
    for name in handmade_schema_names():
        annotations = read_schema_annotations(name)
        assert annotations["schema_name"] == f"{SCHEMA_PREFIX}{name}"
        assert annotations["edges"], f"{name} annotates no foreign key"


def test_unknown_schema_name_is_rejected() -> None:
    with pytest.raises(BenchmarkFormatError, match="unknown hand-made schema 'bank'"):
        read_schema_script("bank")
    with pytest.raises(BenchmarkFormatError, match="unknown hand-made schema"):
        read_schema_annotations("../shop")


def test_handmade_benchmark_has_about_twenty_handmade_records() -> None:
    records = load_handmade_benchmark()
    assert len(records) >= 20
    assert {record.source for record in records} == {"handmade"}
    assert {record.licence for record in records} == {"MIT"}
    assert all(record.id.startswith("handmade/") for record in records)


def test_every_record_runs_on_a_handmade_schema() -> None:
    schemas = {f"{SCHEMA_PREFIX}{name}" for name in handmade_schema_names()}
    for record in load_handmade_benchmark():
        assert record.schema in schemas, record.id
        assert f"{record.schema}." in record.expected_sql, record.id


def test_every_record_has_patterns_and_stored_rows() -> None:
    for record in load_handmade_benchmark():
        assert record.patterns, f"{record.id} has no pattern"
        assert record.expected_rows is not None, f"{record.id} has no rows"


def test_records_cover_every_required_pattern() -> None:
    covered = {p for record in load_handmade_benchmark() for p in record.patterns}
    assert REQUIRED_PATTERNS <= covered


def test_no_file_links_to_leetcode() -> None:
    for path in HANDMADE_DIRECTORY.iterdir():
        text = path.read_text(encoding="utf-8").lower()
        assert "leetcode" not in text, f"{path.name} mentions LeetCode"

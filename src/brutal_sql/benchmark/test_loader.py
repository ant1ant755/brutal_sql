"""Tests for loading and filtering benchmark JSONL files."""

import json
from pathlib import Path

import pytest

from brutal_sql.benchmark.format import BenchmarkFormatError
from brutal_sql.benchmark.loader import filter_by, load_benchmark

SAMPLE_FILE = Path(__file__).with_name("sample_benchmark.jsonl")


def record_line(record_id: str, **changes: object) -> str:
    """One valid JSONL line, with optional field changes (None removes a field)."""
    data = {
        "id": record_id,
        "source": "handmade",
        "licence": "MIT",
        "schema": "joins_shop",
        "question": "How many customers are there?",
        "expected_sql": "SELECT count(*) FROM joins_shop.customer",
        "ordered": False,
        "patterns": [1],
    }
    data.update(changes)
    return json.dumps({key: value for key, value in data.items() if value is not None})


def write_lines(tmp_path: Path, lines: list[str]) -> Path:
    """Write lines to a bench.jsonl file and return its path."""
    path = tmp_path / "bench.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_load_benchmark_reads_sample_file() -> None:
    records = load_benchmark(SAMPLE_FILE)
    assert [record.id for record in records] == [
        "handmade/sample-001",
        "handmade/sample-002",
        "spider/sample/0001",
        "merged/sample-001",
    ]
    assert records[0].expected_rows == ((5,),)
    assert records[1].ordered is True


def test_load_benchmark_accepts_string_path_and_skips_blank_lines(
    tmp_path: Path,
) -> None:
    path = write_lines(tmp_path, [record_line("a"), "", "   ", record_line("b")])
    assert [record.id for record in load_benchmark(str(path))] == ["a", "b"]


def test_missing_required_field_names_the_line(tmp_path: Path) -> None:
    lines = [record_line("a"), record_line("b"), record_line("c", question=None)]
    path = write_lines(tmp_path, lines)
    with pytest.raises(BenchmarkFormatError, match="bench.jsonl line 3: missing.*"):
        load_benchmark(path)


def test_unknown_pattern_number_names_the_line(tmp_path: Path) -> None:
    path = write_lines(tmp_path, [record_line("a", patterns=[1, 17])])
    with pytest.raises(BenchmarkFormatError, match="line 1: unknown pattern number 17"):
        load_benchmark(path)


def test_unknown_source_names_the_line(tmp_path: Path) -> None:
    path = write_lines(tmp_path, [record_line("a"), record_line("b", source="web")])
    with pytest.raises(BenchmarkFormatError, match="line 2: unknown source 'web'"):
        load_benchmark(path)


def test_bad_json_names_the_line(tmp_path: Path) -> None:
    path = write_lines(tmp_path, [record_line("a"), "{not json"])
    with pytest.raises(BenchmarkFormatError, match="line 2: not valid JSON"):
        load_benchmark(path)


def test_duplicate_id_names_both_lines(tmp_path: Path) -> None:
    path = write_lines(tmp_path, [record_line("a"), record_line("b"), record_line("a")])
    with pytest.raises(BenchmarkFormatError, match="line 3: duplicate id 'a'.*line 1"):
        load_benchmark(path)


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_benchmark(tmp_path / "absent.jsonl")


def test_filter_by_source() -> None:
    records = filter_by(load_benchmark(SAMPLE_FILE), source="handmade")
    assert [record.id for record in records] == [
        "handmade/sample-001",
        "handmade/sample-002",
    ]


def test_filter_by_patterns_keeps_records_with_any_pattern() -> None:
    records = filter_by(load_benchmark(SAMPLE_FILE), patterns=[7, 9])
    assert [record.id for record in records] == [
        "handmade/sample-002",
        "merged/sample-001",
    ]


def test_filter_by_schema() -> None:
    records = filter_by(load_benchmark(SAMPLE_FILE), schema="music_hall")
    assert {record.source for record in records} == {"spider", "merged"}


def test_filter_by_combines_filters() -> None:
    records = filter_by(
        load_benchmark(SAMPLE_FILE), source="spider", patterns=[3], schema="music_hall"
    )
    assert [record.id for record in records] == ["spider/sample/0001"]


def test_filter_by_without_filters_keeps_everything() -> None:
    records = load_benchmark(SAMPLE_FILE)
    assert filter_by(records) == records


def test_filter_by_no_match_returns_empty_list() -> None:
    assert filter_by(load_benchmark(SAMPLE_FILE), patterns=[16]) == []


def test_filter_by_unknown_source_raises() -> None:
    with pytest.raises(BenchmarkFormatError, match="unknown source 'leetcode'"):
        filter_by(load_benchmark(SAMPLE_FILE), source="leetcode")


def test_filter_by_unknown_pattern_raises() -> None:
    with pytest.raises(BenchmarkFormatError, match="unknown pattern number 0"):
        filter_by(load_benchmark(SAMPLE_FILE), patterns=[0])

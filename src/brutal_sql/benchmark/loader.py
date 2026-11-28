"""Load benchmark JSON Lines files and filter their records."""

import json
from collections.abc import Iterable
from pathlib import Path

from brutal_sql.benchmark.format import (
    BenchmarkFormatError,
    BenchmarkRecord,
    record_from_dict,
    require_known_source,
    require_pattern_numbers,
)


def _parse_line(text: str, line_number: int, file_name: str) -> BenchmarkRecord:
    """Parse one JSONL line into a record; errors name the file and line."""
    try:
        return record_from_dict(json.loads(text))
    except json.JSONDecodeError as error:
        raise BenchmarkFormatError(
            f"{file_name} line {line_number}: not valid JSON ({error.msg})"
        ) from error
    except BenchmarkFormatError as error:
        raise BenchmarkFormatError(
            f"{file_name} line {line_number}: {error}"
        ) from error


def _reject_duplicate_ids(
    numbered_records: list[tuple[int, BenchmarkRecord]], file_name: str
) -> None:
    """Raise BenchmarkFormatError if two lines share a record id."""
    first_line_by_id: dict[str, int] = {}
    for line_number, record in numbered_records:
        if record.id in first_line_by_id:
            raise BenchmarkFormatError(
                f"{file_name} line {line_number}: duplicate id {record.id!r} "
                f"(first seen on line {first_line_by_id[record.id]})"
            )
        first_line_by_id[record.id] = line_number


def load_benchmark(path: Path | str) -> list[BenchmarkRecord]:
    """Read a benchmark JSONL file and return its validated records in order.

    Blank lines are skipped. Any bad line raises BenchmarkFormatError naming
    the file and line number. A missing file raises FileNotFoundError.
    """
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered_records = [
        (number, _parse_line(text, number, path.name))
        for number, text in enumerate(lines, start=1)
        if text.strip()
    ]
    _reject_duplicate_ids(numbered_records, path.name)
    return [record for _, record in numbered_records]


def _matches(
    record: BenchmarkRecord,
    source: str | None,
    patterns: tuple[int, ...] | None,
    schema: str | None,
) -> bool:
    """True when the record passes every filter that is set."""
    if source is not None and record.source != source:
        return False
    if schema is not None and record.schema != schema:
        return False
    if patterns is not None and not set(patterns) & set(record.patterns):
        return False
    return True


def filter_by(
    records: Iterable[BenchmarkRecord],
    source: str | None = None,
    patterns: Iterable[int] | None = None,
    schema: str | None = None,
) -> list[BenchmarkRecord]:
    """Keep records matching every filter given; None means no filter.

    patterns keeps records that use any of the given pattern numbers. An
    unknown source or pattern number raises BenchmarkFormatError.
    """
    if source is not None:
        require_known_source(source)
    wanted_patterns = None if patterns is None else tuple(patterns)
    if wanted_patterns is not None:
        require_pattern_numbers(wanted_patterns)
    return [
        record
        for record in records
        if _matches(record, source, wanted_patterns, schema)
    ]

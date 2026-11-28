"""The benchmark record: one question with its expected SQL, rows and patterns."""

from dataclasses import asdict, dataclass, fields
from typing import Any

KNOWN_SOURCES = ("spider", "handmade", "merged")
PATTERN_NUMBERS = range(1, 17)
REQUIRED_FIELDS = (
    "id",
    "source",
    "licence",
    "schema",
    "question",
    "expected_sql",
    "ordered",
    "patterns",
)


class BenchmarkFormatError(ValueError):
    """Raised when a benchmark record or file does not follow the format."""


def _require_text(value: object, field_name: str) -> None:
    """Raise BenchmarkFormatError unless value is a non-blank string."""
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkFormatError(
            f"{field_name} must be a non-blank string, got {value!r}"
        )


def require_known_source(source: object) -> None:
    """Raise BenchmarkFormatError unless source is one of KNOWN_SOURCES."""
    if source not in KNOWN_SOURCES:
        raise BenchmarkFormatError(
            f"unknown source {source!r}, expected one of {', '.join(KNOWN_SOURCES)}"
        )


def require_pattern_numbers(patterns: object) -> None:
    """Raise BenchmarkFormatError unless patterns holds distinct ints 1-16."""
    if not isinstance(patterns, tuple):
        raise BenchmarkFormatError(f"patterns must be a list, got {patterns!r}")
    for pattern in patterns:
        is_int = isinstance(pattern, int) and not isinstance(pattern, bool)
        if not is_int or pattern not in PATTERN_NUMBERS:
            raise BenchmarkFormatError(
                f"unknown pattern number {pattern!r}, expected an integer 1-16"
            )
    if len(set(patterns)) != len(patterns):
        raise BenchmarkFormatError(f"patterns repeat a number: {list(patterns)}")


def _require_flag(value: object, field_name: str) -> None:
    """Raise BenchmarkFormatError unless value is a bool."""
    if not isinstance(value, bool):
        raise BenchmarkFormatError(f"{field_name} must be true or false, got {value!r}")


def _require_optional_object(value: object, field_name: str) -> None:
    """Raise BenchmarkFormatError unless value is None or a JSON object."""
    if value is not None and not isinstance(value, dict):
        raise BenchmarkFormatError(f"{field_name} must be an object, got {value!r}")


def _require_optional_rows(rows: object) -> None:
    """Raise BenchmarkFormatError unless rows is None or a tuple of row tuples."""
    if rows is None:
        return
    if not isinstance(rows, tuple) or not all(isinstance(r, tuple) for r in rows):
        raise BenchmarkFormatError(
            f"expected_rows must be a list of rows, got {rows!r}"
        )


@dataclass(frozen=True)
class BenchmarkRecord:
    """One benchmark question, validated on creation.

    expected_rows is None until B.04 / B.07 fill it in; expected_tree and
    expected_shape are optional and filled by later build tickets.
    """

    id: str
    source: str
    licence: str
    schema: str
    question: str
    expected_sql: str
    ordered: bool
    patterns: tuple[int, ...]
    expected_rows: tuple[tuple[Any, ...], ...] | None = None
    expected_tree: dict[str, Any] | None = None
    expected_shape: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("id", "licence", "schema", "question", "expected_sql"):
            _require_text(getattr(self, name), name)
        require_known_source(self.source)
        _require_flag(self.ordered, "ordered")
        require_pattern_numbers(self.patterns)
        _require_optional_rows(self.expected_rows)
        _require_optional_object(self.expected_tree, "expected_tree")
        _require_optional_object(self.expected_shape, "expected_shape")


def _as_tuple(value: object) -> object:
    """Turn a JSON list into a tuple; leave anything else unchanged."""
    return tuple(value) if isinstance(value, list) else value


def _as_rows(value: object) -> object:
    """Turn a JSON list of row lists into a tuple of tuples."""
    if not isinstance(value, list):
        return value
    return tuple(_as_tuple(row) for row in value)


def record_from_dict(data: object) -> BenchmarkRecord:
    """Build a validated BenchmarkRecord from one parsed JSON object."""
    if not isinstance(data, dict):
        raise BenchmarkFormatError(f"a record must be a JSON object, got {data!r}")
    missing = [name for name in REQUIRED_FIELDS if name not in data]
    if missing:
        raise BenchmarkFormatError(f"missing required field: {', '.join(missing)}")
    known = {field.name for field in fields(BenchmarkRecord)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise BenchmarkFormatError(f"unknown field: {', '.join(unknown)}")
    values = dict(data)
    values["patterns"] = _as_tuple(values["patterns"])
    values["expected_rows"] = _as_rows(values.get("expected_rows"))
    return BenchmarkRecord(**values)


def record_to_dict(record: BenchmarkRecord) -> dict[str, Any]:
    """Turn a record back into a JSON-ready dict (tuples become lists)."""
    data = asdict(record)
    data["patterns"] = list(record.patterns)
    if record.expected_rows is not None:
        data["expected_rows"] = [list(row) for row in record.expected_rows]
    return data

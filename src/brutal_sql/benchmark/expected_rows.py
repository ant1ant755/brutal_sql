"""Run a record's expected SQL and compare result rows with the stored ones."""

import dataclasses
import datetime
from collections import Counter
from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection

from brutal_sql.benchmark.format import BenchmarkFormatError, BenchmarkRecord

Rows = tuple[tuple[Any, ...], ...]
PLAIN_JSON_TYPES = (str, int, float, bool, type(None))


def json_ready_value(value: object) -> Any:
    """Turn one database value into a JSON value.

    Decimal becomes float and dates and times become ISO strings. Any other
    type that JSON can't hold raises BenchmarkFormatError.
    """
    if isinstance(value, PLAIN_JSON_TYPES):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    raise BenchmarkFormatError(
        f"cannot store a {type(value).__name__} value in expected_rows"
    )


def json_ready_rows(rows: Iterable[Sequence[Any]]) -> Rows:
    """Turn every value of every row into a JSON value."""
    return tuple(tuple(json_ready_value(value) for value in row) for row in rows)


def run_expected_sql(connection: Connection, sql: str) -> Rows:
    """Run sql and return its rows as tuples of JSON values."""
    return json_ready_rows(connection.exec_driver_sql(sql).fetchall())


def rows_match(expected: Rows, actual: Rows, ordered: bool) -> bool:
    """True when the rows are equal; order counts only when ordered is True.

    Unordered rows are compared as a multiset, so duplicates must match too.
    """
    if ordered:
        return tuple(expected) == tuple(actual)
    return Counter(map(tuple, expected)) == Counter(map(tuple, actual))


def fill_expected_rows(
    connection: Connection, records: Iterable[BenchmarkRecord]
) -> list[BenchmarkRecord]:
    """Return copies of the records with expected_rows from running their SQL."""
    return [
        dataclasses.replace(
            record, expected_rows=run_expected_sql(connection, record.expected_sql)
        )
        for record in records
    ]

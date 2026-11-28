"""Unit tests for running expected SQL and comparing result rows."""

import datetime
from decimal import Decimal
from typing import Any

import pytest

from brutal_sql.benchmark.expected_rows import (
    fill_expected_rows,
    json_ready_rows,
    json_ready_value,
    rows_match,
    run_expected_sql,
)
from brutal_sql.benchmark.format import BenchmarkFormatError, BenchmarkRecord


class FakeResult:
    """Stands in for a SQLAlchemy result with fixed rows."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class FakeConnection:
    """Stands in for a connection; returns rows per SQL text and records calls."""

    def __init__(self, rows_by_sql: dict[str, list[tuple[Any, ...]]]) -> None:
        self.rows_by_sql = rows_by_sql
        self.executed: list[str] = []

    def exec_driver_sql(self, sql: str) -> FakeResult:
        self.executed.append(sql)
        return FakeResult(self.rows_by_sql[sql])


def make_record(sql: str) -> BenchmarkRecord:
    """A valid handmade record running sql."""
    return BenchmarkRecord(
        id=f"handmade/{sql}",
        source="handmade",
        licence="MIT",
        schema="handmade_shop",
        question="q?",
        expected_sql=sql,
        ordered=False,
        patterns=(1,),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("text", "text"),
        (3, 3),
        (2.5, 2.5),
        (True, True),
        (None, None),
        (Decimal("6166.67"), 6166.67),
        (datetime.date(2026, 3, 1), "2026-03-01"),
        (datetime.datetime(2026, 3, 1, 9, 30), "2026-03-01T09:30:00"),
        (datetime.time(9, 30), "09:30:00"),
    ],
)
def test_json_ready_value_converts_supported_types(
    value: object, expected: Any
) -> None:
    assert json_ready_value(value) == expected


@pytest.mark.parametrize("value", [b"bytes", [1, 2], {"a": 1}])
def test_json_ready_value_rejects_other_types(value: object) -> None:
    with pytest.raises(BenchmarkFormatError, match="cannot store"):
        json_ready_value(value)


def test_json_ready_rows_converts_every_value() -> None:
    rows = [(1, Decimal("2.50")), (2, datetime.date(2026, 1, 2))]
    assert json_ready_rows(rows) == ((1, 2.5), (2, "2026-01-02"))


def test_rows_match_ignores_order_when_unordered() -> None:
    assert rows_match(((1,), (2,)), ((2,), (1,)), ordered=False)


def test_rows_match_checks_order_when_ordered() -> None:
    assert rows_match(((1,), (2,)), ((1,), (2,)), ordered=True)
    assert not rows_match(((1,), (2,)), ((2,), (1,)), ordered=True)


def test_rows_match_counts_duplicates() -> None:
    assert not rows_match(((1,), (1,)), ((1,),), ordered=False)
    assert not rows_match(((1,), (1,), (2,)), ((1,), (2,), (2,)), ordered=False)


def test_rows_match_rejects_different_values() -> None:
    assert not rows_match((("Ana", 9000),), (("Ana", 9001),), ordered=False)


def test_run_expected_sql_returns_json_ready_rows() -> None:
    connection = FakeConnection({"SELECT 1": [(Decimal("1.5"),)]})
    rows = run_expected_sql(connection, "SELECT 1")  # type: ignore[arg-type]
    assert rows == ((1.5,),)


def test_fill_expected_rows_runs_each_record() -> None:
    connection = FakeConnection({"A": [(1,)], "B": []})
    records = fill_expected_rows(
        connection, [make_record("A"), make_record("B")]  # type: ignore[arg-type]
    )
    assert [record.expected_rows for record in records] == [((1,),), ()]
    assert connection.executed == ["A", "B"]


def test_fill_expected_rows_rejects_unstorable_value() -> None:
    connection = FakeConnection({"A": [(b"blob",)]})
    with pytest.raises(BenchmarkFormatError, match="cannot store a bytes"):
        fill_expected_rows(connection, [make_record("A")])  # type: ignore[arg-type]

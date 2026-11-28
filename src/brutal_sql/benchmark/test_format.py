"""Tests for the benchmark record format."""

import pytest

from brutal_sql.benchmark.format import (
    BenchmarkFormatError,
    BenchmarkRecord,
    record_from_dict,
    record_to_dict,
)


def valid_record_data() -> dict:
    """A complete, valid record as parsed from JSON."""
    return {
        "id": "handmade/test-001",
        "source": "handmade",
        "licence": "MIT",
        "schema": "joins_shop",
        "question": "How many customers are there?",
        "expected_sql": "SELECT count(*) FROM joins_shop.customer",
        "ordered": False,
        "patterns": [1, 4],
    }


def test_record_from_dict_builds_record_with_tuples() -> None:
    data = valid_record_data() | {"expected_rows": [[5], [6]]}
    record = record_from_dict(data)
    assert record.id == "handmade/test-001"
    assert record.patterns == (1, 4)
    assert record.expected_rows == ((5,), (6,))


def test_optional_fields_default_to_none() -> None:
    record = record_from_dict(valid_record_data())
    assert record.expected_rows is None
    assert record.expected_tree is None
    assert record.expected_shape is None


def test_empty_patterns_are_allowed_until_classified() -> None:
    record = record_from_dict(valid_record_data() | {"patterns": []})
    assert record.patterns == ()


def test_record_round_trips_through_dict() -> None:
    data = valid_record_data() | {
        "expected_rows": [["a", 1]],
        "expected_tree": {"kind": "join"},
    }
    record = record_from_dict(data)
    assert record_from_dict(record_to_dict(record)) == record
    assert record_to_dict(record)["expected_rows"] == [["a", 1]]


def test_missing_required_field_is_named() -> None:
    data = valid_record_data()
    del data["question"]
    with pytest.raises(BenchmarkFormatError, match="missing required field: question"):
        record_from_dict(data)


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(BenchmarkFormatError, match="unknown field: qestion"):
        record_from_dict(valid_record_data() | {"qestion": "typo"})


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(BenchmarkFormatError, match="unknown source 'leetcode'"):
        record_from_dict(valid_record_data() | {"source": "leetcode"})


@pytest.mark.parametrize("pattern", [0, 17, "3", True, 2.0])
def test_unknown_pattern_number_is_rejected(pattern: object) -> None:
    with pytest.raises(BenchmarkFormatError, match="unknown pattern number"):
        record_from_dict(valid_record_data() | {"patterns": [1, pattern]})


def test_repeated_pattern_number_is_rejected() -> None:
    with pytest.raises(BenchmarkFormatError, match="repeat"):
        record_from_dict(valid_record_data() | {"patterns": [2, 2]})


def test_patterns_must_be_a_list() -> None:
    with pytest.raises(BenchmarkFormatError, match="patterns must be a list"):
        record_from_dict(valid_record_data() | {"patterns": 3})


def test_ordered_must_be_a_bool() -> None:
    with pytest.raises(BenchmarkFormatError, match="ordered must be true or false"):
        record_from_dict(valid_record_data() | {"ordered": "yes"})


@pytest.mark.parametrize("field", ["id", "licence", "schema", "expected_sql"])
def test_blank_text_field_is_rejected(field: str) -> None:
    with pytest.raises(BenchmarkFormatError, match=f"{field} must be a non-blank"):
        record_from_dict(valid_record_data() | {field: "  "})


def test_expected_rows_must_be_rows() -> None:
    with pytest.raises(BenchmarkFormatError, match="expected_rows"):
        record_from_dict(valid_record_data() | {"expected_rows": [1, 2]})


def test_expected_tree_must_be_an_object() -> None:
    with pytest.raises(BenchmarkFormatError, match="expected_tree"):
        record_from_dict(valid_record_data() | {"expected_tree": "join"})


def test_record_must_be_a_json_object() -> None:
    with pytest.raises(BenchmarkFormatError, match="JSON object"):
        record_from_dict(["not", "a", "record"])


def test_record_is_validated_when_built_directly() -> None:
    with pytest.raises(BenchmarkFormatError, match="unknown source"):
        BenchmarkRecord(
            id="x",
            source="other",
            licence="MIT",
            schema="s",
            question="q",
            expected_sql="SELECT 1",
            ordered=False,
            patterns=(),
        )


def test_record_to_dict_rejects_non_record() -> None:
    with pytest.raises(TypeError):
        record_to_dict(valid_record_data())  # type: ignore[arg-type]

"""Tests for turning composite foreign keys into graph edges (no database)."""

import logging

import pytest

from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.schema_to_graph import (
    BACKWARD_VERB,
    FORWARD_VERB,
    add_foreign_key_edges,
    build_entity_node,
    convert_tables_to_graph,
)
from brutal_sql.graph import EdgeType, Graph

SCHEMA = "lines"
KEY = ("order_id", "line_no")


def table(
    name: str, columns: list[str], keys: tuple[ForeignKeyMetadata, ...] = ()
) -> TableMetadata:
    return TableMetadata(
        name, tuple(ColumnMetadata(c, "INTEGER") for c in columns), (), (), keys
    )


def lines_key(schema: str = SCHEMA, table_name: str = "order_lines") -> tuple:
    return (ForeignKeyMetadata(KEY, schema, table_name, KEY),)


def lines_tables(keys: tuple[ForeignKeyMetadata, ...]) -> list[TableMetadata]:
    return [
        table("order_lines", [*KEY, "sku"]),
        table("shipments", ["id", *KEY], keys),
    ]


def test_composite_key_becomes_one_edge_each_way() -> None:
    graph = convert_tables_to_graph(SCHEMA, lines_tables(lines_key()))
    (forward,) = graph.get_node("shipments").edges
    (backward,) = graph.get_node("order_lines").edges
    assert (forward.edge_type, forward.verb_label) == (EdgeType.FORWARD, FORWARD_VERB)
    assert (backward.edge_type, backward.verb_label) == (
        EdgeType.BACKWARD,
        BACKWARD_VERB,
    )
    assert forward.column_pairs == (("order_id", "order_id"), ("line_no", "line_no"))
    assert backward.target_table == "shipments"


def test_repeated_composite_key_is_skipped(caplog: pytest.LogCaptureFixture) -> None:
    tables = lines_tables(lines_key() * 2)
    graph = Graph(SCHEMA, [build_entity_node(t) for t in tables])
    with caplog.at_level(logging.WARNING):
        assert add_foreign_key_edges(graph, tables[1]) == 1
    assert len(graph.get_node("shipments").edges) == 1
    assert "already added" in caplog.text


def test_keys_sharing_first_column_are_both_added() -> None:
    keys = (
        ForeignKeyMetadata(KEY, SCHEMA, "order_lines", KEY),
        ForeignKeyMetadata(("order_id",), SCHEMA, "order_lines", ("order_id",)),
    )
    graph = convert_tables_to_graph(SCHEMA, lines_tables(keys))
    pairs = [edge.column_pairs for edge in graph.get_node("shipments").edges]
    assert pairs == [
        (("order_id", "order_id"), ("line_no", "line_no")),
        (("order_id", "order_id"),),
    ]


@pytest.mark.parametrize(
    "keys, reason",
    [
        (lines_key(schema="crm"), "schema 'crm'"),
        (lines_key(table_name="shipments"), "self join"),
    ],
)
def test_cross_schema_and_self_composite_keys_are_still_skipped(
    keys: tuple, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        graph = convert_tables_to_graph(SCHEMA, lines_tables(keys))
    assert graph.get_node("shipments").edges == []
    assert reason in caplog.text


def test_composite_key_to_missing_column_raises_processing_error() -> None:
    keys = (ForeignKeyMetadata(KEY, SCHEMA, "order_lines", ("order_id", "ghost")),)
    with pytest.raises(ProcessingError, match="ghost") as caught:
        convert_tables_to_graph(SCHEMA, lines_tables(keys))
    assert caught.value.__cause__ is not None

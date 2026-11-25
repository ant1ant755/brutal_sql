"""Tests for turning table metadata into an entity graph (no database)."""

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
    readable_name_for,
)
from brutal_sql.graph import EdgeType, Graph

SCHEMA = "shop"


def column(name: str, comment: str | None = None) -> ColumnMetadata:
    return ColumnMetadata(name, "INTEGER", comment=comment)


def foreign_key(
    columns: tuple[str, ...],
    table: str,
    referred: tuple[str, ...] = ("id",),
    schema: str = SCHEMA,
) -> ForeignKeyMetadata:
    return ForeignKeyMetadata(columns, schema, table, referred)


def table(
    name: str, columns: list[str], keys: tuple[ForeignKeyMetadata, ...] = ()
) -> TableMetadata:
    return TableMetadata(name, tuple(column(c) for c in columns), ("id",), (), keys)


def shop_tables() -> list[TableMetadata]:
    return [
        table("customers", ["id", "full_name"]),
        table(
            "orders",
            ["id", "customer_id"],
            (foreign_key(("customer_id",), "customers"),),
        ),
    ]


def test_readable_name_prefers_comment() -> None:
    assert readable_name_for(column("cid", "  cookie id ")) == "cookie id"


@pytest.mark.parametrize("comment", [None, "", "   "])
def test_readable_name_falls_back_to_column_name(comment: str | None) -> None:
    assert readable_name_for(column("cid", comment)) == "cid"


def test_build_entity_node_has_one_attribute_per_column() -> None:
    node = build_entity_node(table("customers", ["id", "full_name"]))
    assert node.name == "customers"
    assert [attribute.name for attribute in node.attributes] == ["id", "full_name"]
    assert node.edges == []


def test_build_entity_node_rejects_non_table() -> None:
    with pytest.raises(AttributeError):
        build_entity_node("customers")  # type: ignore[arg-type]


def test_convert_adds_forward_and_backward_edges() -> None:
    graph = convert_tables_to_graph(SCHEMA, shop_tables())
    (forward,) = graph.get_node("orders").edges
    (backward,) = graph.get_node("customers").edges
    assert (forward.edge_type, forward.verb_label) == (EdgeType.FORWARD, FORWARD_VERB)
    assert (forward.source_field, forward.target_table) == ("customer_id", "customers")
    assert (backward.edge_type, backward.verb_label) == (
        EdgeType.BACKWARD,
        BACKWARD_VERB,
    )
    assert (backward.target_table, backward.target_table_field) == (
        "orders",
        "customer_id",
    )


def test_convert_rejects_empty_table_list() -> None:
    with pytest.raises(ProcessingError):
        convert_tables_to_graph(SCHEMA, [])


def test_convert_wraps_graph_errors_for_unknown_referred_table() -> None:
    orphan = table(
        "orders", ["id", "ghost_id"], (foreign_key(("ghost_id",), "ghosts"),)
    )
    with pytest.raises(ProcessingError, match="ghosts") as caught:
        convert_tables_to_graph(SCHEMA, [orphan])
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize(
    "key, reason",
    [
        (foreign_key(("manager_id",), "employees"), "self join"),
        (foreign_key(("a", "b"), "customers", ("id", "full_name")), "more than one"),
        (foreign_key(("customer_id",), "customers", schema="crm"), "schema 'crm'"),
    ],
)
def test_add_edges_skips_unsupported_foreign_keys(
    key: ForeignKeyMetadata, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    employees = table(
        "employees", ["id", "manager_id", "a", "b", "customer_id"], (key,)
    )
    graph = Graph(SCHEMA, [build_entity_node(t) for t in [*shop_tables(), employees]])
    with caplog.at_level(logging.WARNING):
        assert add_foreign_key_edges(graph, employees) == 0
    assert graph.get_node("employees").edges == []
    assert reason in caplog.text


def test_add_edges_skips_repeated_foreign_key(caplog: pytest.LogCaptureFixture) -> None:
    key = foreign_key(("customer_id",), "customers")
    orders = table("orders", ["id", "customer_id"], (key, key))
    graph = Graph(SCHEMA, [build_entity_node(t) for t in [shop_tables()[0], orders]])
    with caplog.at_level(logging.WARNING):
        assert add_foreign_key_edges(graph, orders) == 1
    assert len(graph.get_node("orders").edges) == 1
    assert "already added" in caplog.text

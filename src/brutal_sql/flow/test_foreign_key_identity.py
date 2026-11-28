"""Tests for naming foreign keys and reading their nullability (no database)."""

import pytest

from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.foreign_key_identity import edge_id_for, is_foreign_key_nullable
from brutal_sql.flow.schema_to_graph import convert_tables_to_graph
from brutal_sql.graph import EdgeType, Graph

SCHEMA = "shop"


def column(name: str, nullable: bool = True) -> ColumnMetadata:
    return ColumnMetadata(name, "INTEGER", nullable=nullable)


def key(
    columns: tuple[str, ...],
    table: str,
    referred: tuple[str, ...] = ("id",),
    name: str | None = None,
) -> ForeignKeyMetadata:
    return ForeignKeyMetadata(columns, SCHEMA, table, referred, name)


BILLING_KEY = key(("billing_address_id",), "address", name="orders_billing_fkey")
SHIPPING_KEY = key(("shipping_address_id",), "address", name="orders_shipping_fkey")
LINE_KEY = key(("order_id", "line_no"), "order_lines", ("order_id", "line_no"))


def orders(*keys: ForeignKeyMetadata) -> TableMetadata:
    columns = (
        column("id", nullable=False),
        column("billing_address_id", nullable=False),
        column("shipping_address_id"),
        column("order_id", nullable=False),
        column("line_no"),
    )
    return TableMetadata("orders", columns, ("id",), (), keys)


def test_edge_id_is_the_constraint_name() -> None:
    assert edge_id_for(orders(), BILLING_KEY) == "orders_billing_fkey"


@pytest.mark.parametrize(
    "foreign_key, expected",
    [
        (
            key(("billing_address_id",), "address"),
            "orders(billing_address_id)->address(id)",
        ),
        (LINE_KEY, "orders(order_id,line_no)->order_lines(order_id,line_no)"),
        (
            key(("billing_address_id",), "address", name="  "),
            "orders(billing_address_id)->address(id)",
        ),
    ],
)
def test_edge_id_without_a_name_is_built_from_columns(
    foreign_key: ForeignKeyMetadata, expected: str
) -> None:
    assert edge_id_for(orders(), foreign_key) == expected
    assert edge_id_for(orders(), foreign_key) == edge_id_for(orders(), foreign_key)


def test_nullable_column_gives_nullable_key() -> None:
    assert is_foreign_key_nullable(orders(), SHIPPING_KEY) is True


def test_not_null_column_gives_not_nullable_key() -> None:
    assert is_foreign_key_nullable(orders(), BILLING_KEY) is False


def test_composite_key_is_nullable_when_any_column_is() -> None:
    assert is_foreign_key_nullable(orders(), LINE_KEY) is True


def test_nullable_rejects_column_missing_from_table() -> None:
    with pytest.raises(ProcessingError, match="ghost_id"):
        is_foreign_key_nullable(orders(), key(("ghost_id",), "address"))


def shop_tables() -> list[TableMetadata]:
    address = TableMetadata("address", (column("id", nullable=False),), ("id",))
    return [address, orders(BILLING_KEY, SHIPPING_KEY)]


def identities(graph: Graph, edge_type: EdgeType) -> set[tuple[str, str, bool]]:
    return {
        (edge.source_field, edge.edge_id, edge.nullable)
        for node in graph.nodes
        for edge in node.edges
        if edge.edge_type == edge_type
    }


def test_conversion_labels_every_edge_with_its_foreign_key() -> None:
    graph = convert_tables_to_graph(SCHEMA, shop_tables())
    assert identities(graph, EdgeType.FORWARD) == {
        ("billing_address_id", "orders_billing_fkey", False),
        ("shipping_address_id", "orders_shipping_fkey", True),
    }
    assert identities(graph, EdgeType.BACKWARD) == {
        ("id", "orders_billing_fkey", False),
        ("id", "orders_shipping_fkey", True),
    }


def test_conversion_rejects_key_on_missing_column() -> None:
    address = TableMetadata("address", (column("id"),), ("id",))
    broken = orders(key(("ghost_id",), "address"))
    with pytest.raises(ProcessingError, match="ghost_id"):
        convert_tables_to_graph(SCHEMA, [address, broken])


def test_mirror_edges_carry_the_self_reference_name_and_nullability() -> None:
    manager_key = ForeignKeyMetadata(
        ("manager_id",), SCHEMA, "employee", ("id",), "employee_manager_id_fkey"
    )
    employee = TableMetadata(
        "employee",
        (column("id", nullable=False), column("manager_id")),
        ("id",),
        (),
        (manager_key,),
    )
    graph = convert_tables_to_graph(SCHEMA, [employee])
    labels = {
        (node.name, edge.edge_id, edge.nullable)
        for node in graph.nodes
        for edge in node.edges
    }
    assert labels == {
        ("employee", "employee_manager_id_fkey", True),
        ("managers", "employee_manager_id_fkey", True),
    }

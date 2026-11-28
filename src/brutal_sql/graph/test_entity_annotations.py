"""Tests for the table type of a node and the role name of an edge."""

import pytest

from brutal_sql.graph import (
    Edge,
    EdgeType,
    EntityAttribute,
    EntityNode,
    GraphError,
    TableType,
)


def make_edge(role_name: object = None) -> Edge:
    return Edge(
        "billing_address_id",
        "address",
        "id",
        "billed to",
        EdgeType.FORWARD,
        edge_id="orders_billing_fkey",
        role_name=role_name,  # type: ignore[arg-type]
    )


def test_node_has_no_table_type_by_default() -> None:
    assert EntityNode("orders", [EntityAttribute("id", "id")]).table_type is None


def test_node_keeps_a_valid_table_type() -> None:
    node = EntityNode(
        "orders", [EntityAttribute("id", "id")], table_type=TableType.DIMENSION
    )
    assert node.table_type is TableType.DIMENSION


@pytest.mark.parametrize("bad_type", ["entity", "fact", 1])
def test_node_rejects_a_table_type_that_is_not_a_table_type(bad_type: object) -> None:
    with pytest.raises(GraphError, match="table_type must be a TableType"):
        EntityNode(
            "orders",
            [EntityAttribute("id", "id")],
            table_type=bad_type,  # type: ignore[arg-type]
        )


def test_edge_has_no_role_name_by_default() -> None:
    assert make_edge().role_name is None


def test_edge_keeps_a_role_name() -> None:
    assert make_edge("billing").role_name == "billing"


@pytest.mark.parametrize("bad_role", ["", "   ", 7])
def test_edge_rejects_a_blank_or_non_text_role_name(bad_role: object) -> None:
    with pytest.raises(GraphError, match="role_name"):
        make_edge(bad_role)

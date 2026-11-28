"""Tests for the edge_id and nullable fields that every foreign key edge carries."""

import pytest

from brutal_sql.graph import (
    Edge,
    EdgeType,
    EntityAttribute,
    EntityNode,
    Graph,
    GraphError,
)
from brutal_sql.graph.foreign_key_edges import build_foreign_key_edges


def make_graph() -> Graph:
    address = EntityNode("address", [EntityAttribute("id", "id")])
    orders = EntityNode(
        "orders",
        [
            EntityAttribute("id", "id"),
            EntityAttribute("billing_address_id", "billing address"),
            EntityAttribute("shipping_address_id", "shipping address"),
        ],
    )
    return Graph("shop", [address, orders])


def add_address_key(graph: Graph, column: str, edge_id: str, nullable: bool) -> None:
    graph.add_foreign_key(
        "orders",
        column,
        "address",
        "id",
        "billed to",
        "bills",
        edge_id=edge_id,
        nullable=nullable,
    )


def test_edge_keeps_edge_id_and_nullable() -> None:
    edge = Edge(
        "customer_id",
        "customers",
        "id",
        "placed by",
        EdgeType.FORWARD,
        edge_id="orders_customer_id_fkey",
        nullable=True,
    )
    assert edge.edge_id == "orders_customer_id_fkey"
    assert edge.nullable is True


def test_edge_defaults_to_no_edge_id_and_not_nullable() -> None:
    edge = Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)
    assert edge.edge_id is None
    assert edge.nullable is False


@pytest.mark.parametrize("edge_id", ["", "   ", 7, ["fk"]])
def test_edge_rejects_blank_or_non_text_edge_id(edge_id: object) -> None:
    with pytest.raises(GraphError, match="edge_id"):
        Edge("a", "b", "c", "verb", EdgeType.FORWARD, edge_id=edge_id)  # type: ignore


@pytest.mark.parametrize("nullable", ["yes", 1, 0, None])
def test_edge_rejects_non_bool_nullable(nullable: object) -> None:
    with pytest.raises(GraphError, match="nullable"):
        Edge("a", "b", "c", "verb", EdgeType.FORWARD, nullable=nullable)  # type: ignore


def test_edges_differing_only_by_edge_id_are_not_equal() -> None:
    first = Edge("a", "b", "c", "verb", EdgeType.FORWARD, edge_id="fk_one")
    second = Edge("a", "b", "c", "verb", EdgeType.FORWARD, edge_id="fk_two")
    assert first != second


def test_build_foreign_key_edges_share_edge_id_and_nullable() -> None:
    forward, backward = build_foreign_key_edges(
        "orders",
        [("billing_address_id", "id")],
        "address",
        ("billed to", "bills"),
        edge_id="orders_billing_fkey",
        nullable=True,
    )
    assert forward.edge_id == backward.edge_id == "orders_billing_fkey"
    assert forward.nullable is backward.nullable is True


def test_build_foreign_key_edges_rejects_blank_edge_id() -> None:
    with pytest.raises(GraphError, match="edge_id"):
        build_foreign_key_edges(
            "orders", [("billing_address_id", "id")], "address", ("a", "b"), edge_id=""
        )


def test_add_foreign_key_labels_both_edges() -> None:
    graph = make_graph()
    add_address_key(graph, "billing_address_id", "orders_billing_fkey", False)
    forward = graph.get_node("orders").edges[0]
    backward = graph.get_node("address").edges[0]
    assert (forward.edge_id, forward.nullable) == ("orders_billing_fkey", False)
    assert (backward.edge_id, backward.nullable) == ("orders_billing_fkey", False)


def test_two_keys_between_same_tables_stay_separate_edges() -> None:
    graph = make_graph()
    add_address_key(graph, "billing_address_id", "orders_billing_fkey", False)
    add_address_key(graph, "shipping_address_id", "orders_shipping_fkey", True)
    for table in ("orders", "address"):
        edges = graph.get_node(table).edges
        assert [edge.edge_id for edge in edges] == [
            "orders_billing_fkey",
            "orders_shipping_fkey",
        ]
        assert [edge.nullable for edge in edges] == [False, True]


def test_add_composite_foreign_key_rejects_non_bool_nullable() -> None:
    graph = make_graph()
    with pytest.raises(GraphError, match="nullable"):
        graph.add_composite_foreign_key(
            "orders",
            ["billing_address_id"],
            "address",
            ["id"],
            "billed to",
            "bills",
            nullable="no",  # type: ignore[arg-type]
        )
    assert graph.get_node("orders").edges == []

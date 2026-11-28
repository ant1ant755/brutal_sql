"""Tests that finding and removing foreign keys matches every column pair."""

import pytest

from brutal_sql.graph import (
    EdgeNotFoundError,
    EdgeType,
    EntityAttribute,
    EntityNode,
    Graph,
    GraphError,
)

ORDER_KEY = (["tenant_id", "order_id"], ["tenant_id", "id"])
RETURN_KEY = (["tenant_id", "return_order_id"], ["tenant_id", "id"])


def make_tenant_graph() -> Graph:
    """Two keys shipments -> orders that share their first pair (tenant_id)."""
    columns = ("id", "tenant_id", "order_id", "return_order_id")
    shipments = EntityNode("shipments", [EntityAttribute(c, c) for c in columns])
    orders = EntityNode(
        "orders", [EntityAttribute(c, c) for c in ("tenant_id", "id", "note")]
    )
    graph = Graph("tenants", [shipments, orders])
    for edge_id, (sources, targets) in [
        ("shipments_order_fkey", ORDER_KEY),
        ("shipments_return_fkey", RETURN_KEY),
    ]:
        graph.add_composite_foreign_key(
            "shipments",
            sources,
            "orders",
            targets,
            "ships",
            "shipped in",
            edge_id=edge_id,
        )
    return graph


def edge_ids(graph: Graph, table: str) -> list[str | None]:
    return [edge.edge_id for edge in graph.get_node(table).edges]


def pairs(key: tuple[list[str], list[str]]) -> list[tuple[str, str]]:
    return list(zip(*key))


@pytest.mark.parametrize(
    "key, edge_id",
    [(ORDER_KEY, "shipments_order_fkey"), (RETURN_KEY, "shipments_return_fkey")],
)
def test_find_edge_along_returns_only_the_matching_key(
    key: tuple[list[str], list[str]], edge_id: str
) -> None:
    graph = make_tenant_graph()
    shipments = graph.get_node("shipments")
    forward = shipments.find_edge_along(EdgeType.FORWARD, "orders", pairs(key))
    assert forward.edge_id == edge_id
    swapped = [(target, source) for source, target in pairs(key)]
    backward = graph.get_node("orders").find_edge_along(
        EdgeType.BACKWARD, "shipments", swapped
    )
    assert backward.edge_id == edge_id


@pytest.mark.parametrize(
    "removed, kept, kept_id",
    [
        (ORDER_KEY, RETURN_KEY, "shipments_return_fkey"),
        (RETURN_KEY, ORDER_KEY, "shipments_order_fkey"),
    ],
)
def test_removing_one_key_removes_both_its_edges_and_keeps_the_other(
    removed: tuple[list[str], list[str]],
    kept: tuple[list[str], list[str]],
    kept_id: str,
) -> None:
    graph = make_tenant_graph()
    forward, backward = graph.remove_composite_foreign_key(
        "shipments", removed[0], "orders", removed[1]
    )
    assert forward.edge_type == EdgeType.FORWARD
    assert backward.edge_type == EdgeType.BACKWARD
    assert forward.column_pairs == tuple(pairs(removed))
    assert edge_ids(graph, "shipments") == [kept_id]
    assert edge_ids(graph, "orders") == [kept_id]
    still_there = graph.get_node("shipments").find_edge_along(
        EdgeType.FORWARD, "orders", pairs(kept)
    )
    assert still_there.edge_id == kept_id


def test_removing_with_different_column_counts_raises_graph_error() -> None:
    graph = make_tenant_graph()
    with pytest.raises(GraphError, match="column counts differ"):
        graph.remove_composite_foreign_key(
            "shipments", ["tenant_id", "order_id"], "orders", ["tenant_id"]
        )
    assert len(graph.get_node("shipments").edges) == 2


@pytest.mark.parametrize(
    "sources, targets",
    [
        (["tenant_id"], ["tenant_id"]),
        (["order_id", "tenant_id"], ["id", "tenant_id"]),
        (["tenant_id", "order_id"], ["tenant_id", "note"]),
    ],
)
def test_removing_a_key_that_does_not_match_exactly_removes_nothing(
    sources: list[str], targets: list[str]
) -> None:
    graph = make_tenant_graph()
    with pytest.raises(EdgeNotFoundError):
        graph.remove_composite_foreign_key("shipments", sources, "orders", targets)
    assert len(graph.get_node("shipments").edges) == 2
    assert len(graph.get_node("orders").edges) == 2


def test_single_column_form_does_not_match_a_composite_edge() -> None:
    graph = make_tenant_graph()
    with pytest.raises(EdgeNotFoundError, match="has no forward edge"):
        graph.get_node("shipments").find_edge(
            EdgeType.FORWARD, "tenant_id", "orders", "tenant_id"
        )
    with pytest.raises(EdgeNotFoundError):
        graph.remove_foreign_key("shipments", "tenant_id", "orders", "tenant_id")
    assert len(graph.get_node("shipments").edges) == 2


def test_missing_backward_edge_removes_nothing() -> None:
    graph = make_tenant_graph()
    orders = graph.get_node("orders")
    backward = orders.find_edge_along(
        EdgeType.BACKWARD, "shipments", [("tenant_id", "tenant_id"), ("id", "order_id")]
    )
    orders.remove_edge(backward)
    with pytest.raises(EdgeNotFoundError):
        graph.remove_composite_foreign_key(
            "shipments", ORDER_KEY[0], "orders", ORDER_KEY[1]
        )
    assert len(graph.get_node("shipments").edges) == 2


def test_single_column_find_and_remove_work_as_before() -> None:
    customers = EntityNode("customers", [EntityAttribute("id", "id")])
    orders = EntityNode(
        "orders", [EntityAttribute("id", "id"), EntityAttribute("customer_id", "c")]
    )
    graph = Graph("shop", [customers, orders])
    graph.add_foreign_key("orders", "customer_id", "customers", "id", "by", "places")
    edge = graph.get_node("orders").find_edge(
        EdgeType.FORWARD, "customer_id", "customers", "id"
    )
    assert edge.verb_label == "by"
    forward, backward = graph.remove_foreign_key(
        "orders", "customer_id", "customers", "id"
    )
    assert (forward.verb_label, backward.verb_label) == ("by", "places")
    assert graph.get_node("orders").edges == []
    assert graph.get_node("customers").edges == []


def test_find_edge_along_rejects_wrong_type_or_table() -> None:
    shipments = make_tenant_graph().get_node("shipments")
    with pytest.raises(EdgeNotFoundError):
        shipments.find_edge_along(EdgeType.BACKWARD, "orders", pairs(ORDER_KEY))
    with pytest.raises(EdgeNotFoundError):
        shipments.find_edge_along(EdgeType.FORWARD, "customers", pairs(ORDER_KEY))

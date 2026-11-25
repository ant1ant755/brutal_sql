"""Tests for the schema graph, using a hand-written orders schema (no database)."""

import pytest

from brutal_sql.graph.entity import Edge, EdgeType, EntityAttribute, EntityNode
from brutal_sql.graph.errors import (
    AttributeNotFoundError,
    DuplicateEdgeError,
    DuplicateNodeError,
    EdgeNotFoundError,
    GraphError,
    NodeNotFoundError,
)
from brutal_sql.graph.schema_graph import Graph, JoinStep

TABLE_COLUMNS = {
    "customers": ["id", "name", "address", "age", "last_order_id"],
    "orders": ["id", "billing_amount", "customer_id", "order_status"],
    "order_items": ["id", "order_id", "product_id", "quantity"],
    "products": ["id", "name", "price"],
}


def make_node(table_name: str, columns: list[str]) -> EntityNode:
    attributes = [
        EntityAttribute(column, column.replace("_", " ")) for column in columns
    ]
    return EntityNode(table_name, attributes)


def make_unlinked_graph() -> Graph:
    nodes = [make_node(table, columns) for table, columns in TABLE_COLUMNS.items()]
    return Graph("shop", nodes)


def make_shop_graph() -> Graph:
    """customers <- orders <- order_items -> products, linked by foreign keys."""
    graph = make_unlinked_graph()
    graph.add_foreign_key(
        "orders", "customer_id", "customers", "id", "placed by", "places"
    )
    graph.add_foreign_key(
        "order_items", "order_id", "orders", "id", "belongs to", "contains"
    )
    graph.add_foreign_key(
        "order_items", "product_id", "products", "id", "refers to", "appears in"
    )
    return graph


def add_last_order_key(graph: Graph) -> None:
    """A second foreign key between customers and orders, on orders.id."""
    graph.add_foreign_key(
        "customers", "last_order_id", "orders", "id", "has last order", "is last of"
    )


def tables_in(path: list[JoinStep]) -> list[str]:
    return [path[0].from_table] + [step.to_table for step in path]


def conditions_in(path: list[JoinStep]) -> list[str]:
    return [step.to_join_condition() for step in path]


# Graph construction and nodes


def test_graph_keeps_schema_name_and_nodes() -> None:
    graph = make_unlinked_graph()
    assert graph.schema_name == "shop"
    assert [node.name for node in graph.nodes] == list(TABLE_COLUMNS)


def test_graph_rejects_empty_node_list() -> None:
    with pytest.raises(GraphError, match="at least one node"):
        Graph("shop", [])


def test_graph_rejects_blank_schema_name() -> None:
    with pytest.raises(GraphError, match="schema_name"):
        Graph("", [make_node("customers", ["id"])])


def test_graph_rejects_duplicate_node_names() -> None:
    with pytest.raises(DuplicateNodeError):
        Graph("shop", [make_node("customers", ["id"]), make_node("customers", ["id"])])


def test_graph_rejects_edge_to_table_not_in_graph() -> None:
    orders = make_node("orders", ["id", "customer_id"])
    orders.add_edge(
        Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)
    )
    with pytest.raises(NodeNotFoundError):
        Graph("shop", [orders])


def test_add_node_adds_node() -> None:
    graph = make_unlinked_graph()
    graph.add_node(make_node("payments", ["id"]))
    assert graph.get_node("payments").name == "payments"


def test_add_node_rejects_duplicate_name() -> None:
    with pytest.raises(DuplicateNodeError):
        make_unlinked_graph().add_node(make_node("orders", ["id"]))


def test_add_node_rejects_edge_to_unknown_column() -> None:
    payments = make_node("payments", ["id", "order_id"])
    payments.add_edge(Edge("order_id", "orders", "uuid", "pays for", EdgeType.FORWARD))
    with pytest.raises(AttributeNotFoundError):
        make_unlinked_graph().add_node(payments)


def test_add_node_rejects_non_node() -> None:
    with pytest.raises(GraphError, match="not an EntityNode"):
        make_unlinked_graph().add_node("payments")


def test_get_node_rejects_unknown_table() -> None:
    with pytest.raises(NodeNotFoundError):
        make_unlinked_graph().get_node("payments")


def test_remove_node_also_removes_edges_pointing_at_it() -> None:
    graph = make_shop_graph()
    removed = graph.remove_node("customers")
    assert removed.name == "customers"
    assert "customers" not in [node.name for node in graph.nodes]
    assert graph.join_options("order_items", "orders") != []
    assert [step.to_table for step in graph.neighbours("orders")] == ["order_items"]


def test_remove_node_rejects_unknown_table() -> None:
    with pytest.raises(NodeNotFoundError):
        make_unlinked_graph().remove_node("payments")


def test_remove_node_rejects_removing_the_last_node() -> None:
    graph = Graph("shop", [make_node("customers", ["id"])])
    with pytest.raises(GraphError, match="last node"):
        graph.remove_node("customers")


# Foreign keys


def test_add_foreign_key_adds_forward_and_backward_edges() -> None:
    graph = make_unlinked_graph()
    graph.add_foreign_key(
        "orders", "customer_id", "customers", "id", "placed by", "places"
    )
    assert graph.get_node("orders").edges == [
        Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)
    ]
    assert graph.get_node("customers").edges == [
        Edge("id", "orders", "customer_id", "places", EdgeType.BACKWARD)
    ]


def test_add_foreign_key_rejects_unknown_table() -> None:
    with pytest.raises(NodeNotFoundError):
        make_unlinked_graph().add_foreign_key(
            "payments", "order_id", "orders", "id", "pays for", "paid by"
        )


def test_add_foreign_key_rejects_unknown_column_and_adds_nothing() -> None:
    graph = make_unlinked_graph()
    with pytest.raises(AttributeNotFoundError):
        graph.add_foreign_key("orders", "customer_id", "customers", "uuid", "a", "b")
    assert graph.get_node("orders").edges == []


def test_add_foreign_key_rejects_duplicate_foreign_key() -> None:
    graph = make_shop_graph()
    with pytest.raises(DuplicateEdgeError):
        graph.add_foreign_key(
            "orders", "customer_id", "customers", "id", "placed by", "places"
        )


def test_remove_foreign_key_removes_both_edges() -> None:
    graph = make_shop_graph()
    graph.remove_foreign_key("orders", "customer_id", "customers", "id")
    assert graph.join_options("orders", "customers") == []
    assert graph.join_options("customers", "orders") == []


def test_remove_foreign_key_rejects_missing_foreign_key() -> None:
    with pytest.raises(EdgeNotFoundError):
        make_unlinked_graph().remove_foreign_key(
            "orders", "customer_id", "customers", "id"
        )


def test_add_foreign_key_rejects_blank_verb_and_adds_nothing() -> None:
    graph = make_unlinked_graph()
    with pytest.raises(GraphError, match="verb_label"):
        graph.add_foreign_key("orders", "customer_id", "customers", "id", "", "places")
    assert graph.get_node("orders").edges == []
    assert graph.get_node("customers").edges == []


def test_self_referencing_foreign_key_adds_both_edges_to_one_node() -> None:
    graph = Graph("hr", [make_node("employees", ["id", "manager_id"])])
    graph.add_foreign_key(
        "employees", "manager_id", "employees", "id", "reports to", "manages"
    )
    verbs = [edge.verb_label for edge in graph.get_node("employees").edges]
    assert verbs == ["reports to", "manages"]
    assert graph.find_all_join_paths_from("employees") == []

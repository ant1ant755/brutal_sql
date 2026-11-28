"""Tests for the join tree model: valid trees and every way a tree can be wrong."""

import pytest

from brutal_sql.graph import (
    Graph,
    GraphError,
    JoinTree,
    JoinTreeError,
    JoinType,
    TreeEdge,
)
from brutal_sql.graph.test_schema_graph import make_unlinked_graph

ORDERS_CUSTOMER = "orders_customer_id_fkey"
ITEMS_ORDER = "order_items_order_id_fkey"
ITEMS_PRODUCT = "order_items_product_id_fkey"


def make_graph() -> Graph:
    """customers <- orders <- order_items -> products, each key with an edge_id."""
    graph = make_unlinked_graph()
    for source, column, target, edge_id in [
        ("orders", "customer_id", "customers", ORDERS_CUSTOMER),
        ("order_items", "order_id", "orders", ITEMS_ORDER),
        ("order_items", "product_id", "products", ITEMS_PRODUCT),
    ]:
        graph.add_foreign_key(source, column, target, "id", "a", "b", edge_id=edge_id)
    return graph


def tree(root: str, tables: list[str], edges: list[TreeEdge]) -> JoinTree:
    return JoinTree(root, tuple(tables), tuple(edges), graph=make_graph())


def test_one_table_tree_is_valid() -> None:
    one = tree("customers", ["customers"], [])
    assert (one.root, one.tables, one.edges) == ("customers", ("customers",), ())


def test_two_table_tree_follows_a_forward_edge() -> None:
    edge = TreeEdge(ORDERS_CUSTOMER, "orders", "customers")
    two = tree("orders", ["orders", "customers"], [edge])
    assert two.edges == (edge,)
    assert edge.join_type is JoinType.INNER and edge.wrapped is False


def test_two_table_tree_follows_a_backward_edge() -> None:
    edge = TreeEdge(ORDERS_CUSTOMER, "customers", "orders", JoinType.LEFT)
    assert tree("customers", ["customers", "orders"], [edge]).edges[0] == edge


def test_three_table_tree_can_branch() -> None:
    edges = [
        TreeEdge(ORDERS_CUSTOMER, "orders", "customers"),
        TreeEdge(ITEMS_ORDER, "orders", "order_items", JoinType.SEMI, wrapped=True),
    ]
    branching = tree("orders", ["orders", "customers", "order_items"], edges)
    assert {edge.child_table for edge in branching.edges} == {
        "customers",
        "order_items",
    }


def test_three_table_tree_can_be_a_chain() -> None:
    edges = [
        TreeEdge(ITEMS_ORDER, "order_items", "orders"),
        TreeEdge(ORDERS_CUSTOMER, "orders", "customers"),
    ]
    assert (
        len(tree("order_items", ["order_items", "orders", "customers"], edges).edges)
        == 2
    )


def test_equal_trees_compare_equal() -> None:
    edge = TreeEdge(ORDERS_CUSTOMER, "orders", "customers")
    assert tree("orders", ["orders", "customers"], [edge]) == tree(
        "orders", ["orders", "customers"], [edge]
    )


def test_loop_is_rejected() -> None:
    graph = make_graph()
    graph.add_foreign_key(
        "customers", "last_order_id", "orders", "id", "a", "b", edge_id="last_fkey"
    )
    edges = (
        TreeEdge(ORDERS_CUSTOMER, "orders", "customers"),
        TreeEdge("last_fkey", "customers", "orders"),
    )
    with pytest.raises(JoinTreeError, match="loop"):
        JoinTree("orders", ("orders", "customers"), edges, graph=graph)


def test_table_with_two_parents_is_rejected_as_a_loop() -> None:
    edges = [
        TreeEdge(ITEMS_ORDER, "order_items", "orders"),
        TreeEdge(ITEMS_PRODUCT, "order_items", "products"),
        TreeEdge(ITEMS_ORDER, "products", "orders"),
    ]
    with pytest.raises(JoinTreeError, match="loop"):
        tree("order_items", ["order_items", "orders", "products", "customers"], edges)


def test_disconnected_table_is_rejected() -> None:
    edges = [TreeEdge(ORDERS_CUSTOMER, "orders", "customers")]
    with pytest.raises(JoinTreeError, match=r"disconnected: \['products'\]"):
        tree("orders", ["orders", "customers", "products"], edges)


def test_unknown_edge_id_is_rejected() -> None:
    edges = [TreeEdge("no_such_fkey", "orders", "customers")]
    with pytest.raises(JoinTreeError, match="unknown edge_id 'no_such_fkey'"):
        tree("orders", ["orders", "customers"], edges)


def test_edge_between_the_wrong_tables_is_rejected() -> None:
    edges = [TreeEdge(ITEMS_ORDER, "orders", "customers")]
    with pytest.raises(JoinTreeError, match="does not join 'orders' to 'customers'"):
        tree("orders", ["orders", "customers"], edges)


def test_root_not_in_the_tree_is_rejected() -> None:
    edges = [TreeEdge(ORDERS_CUSTOMER, "orders", "customers")]
    with pytest.raises(JoinTreeError, match="root 'products' is not a table"):
        tree("products", ["orders", "customers"], edges)


def test_root_as_a_child_is_rejected() -> None:
    edges = [TreeEdge(ORDERS_CUSTOMER, "orders", "customers")]
    with pytest.raises(JoinTreeError, match="cannot be a child"):
        tree("customers", ["orders", "customers"], edges)


def test_edge_using_a_table_outside_the_tree_is_rejected() -> None:
    edges = [TreeEdge(ITEMS_ORDER, "order_items", "orders")]
    with pytest.raises(JoinTreeError, match="not a table of the tree"):
        tree("orders", ["orders", "customers"], edges)


@pytest.mark.parametrize(
    "tables, message",
    [([], "at least one table"), (["orders", "orders"], "twice")],
)
def test_empty_or_repeated_tables_are_rejected(tables: list[str], message: str) -> None:
    with pytest.raises(JoinTreeError, match=message):
        tree("orders", tables, [])


def test_table_not_in_graph_is_rejected() -> None:
    with pytest.raises(JoinTreeError, match="'invoices' is not in the graph"):
        tree("invoices", ["invoices"], [])


def test_tree_edge_to_itself_is_rejected() -> None:
    with pytest.raises(JoinTreeError, match="to itself"):
        TreeEdge(ORDERS_CUSTOMER, "orders", "orders")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"join_type": "inner"}, "join_type must be a JoinType"),
        ({"wrapped": "yes"}, "wrapped must be a bool"),
        ({"edge_id": " "}, "edge_id"),
    ],
)
def test_tree_edge_rejects_bad_fields(changes: dict[str, object], message: str) -> None:
    fields: dict[str, object] = {
        "edge_id": ORDERS_CUSTOMER,
        "parent_table": "orders",
        "child_table": "customers",
    }
    fields.update(changes)
    with pytest.raises(GraphError, match=message):
        TreeEdge(**fields)  # type: ignore[arg-type]


def test_non_tree_edge_is_rejected() -> None:
    with pytest.raises(JoinTreeError, match="not a TreeEdge"):
        not_an_edge: list = [ORDERS_CUSTOMER]
        tree("orders", ["orders", "customers"], not_an_edge)

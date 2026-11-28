"""Tests for spanning trees of a table set (no database)."""

import pytest

from brutal_sql.graph import (
    ForeignKeyLink,
    Graph,
    JoinTree,
    JoinTreeError,
    JoinType,
    NodeNotFoundError,
    find_spanning_trees,
    foreign_keys_within,
)
from brutal_sql.graph.test_join_tree import make_graph
from brutal_sql.graph.test_schema_graph import make_unlinked_graph


def make_two_key_graph() -> Graph:
    """The shop graph plus customers.last_order_id -> orders.id.

    customers and orders are then joined by two foreign keys.
    """
    graph = make_graph()
    graph.add_foreign_key(
        "customers", "last_order_id", "orders", "id", "a", "b", edge_id="last_fkey"
    )
    return graph


def edge_ids(trees: list[JoinTree]) -> list[tuple[str, ...]]:
    """Return the edge_ids of each tree, in tree order."""
    return [tuple(edge.edge_id for edge in tree.edges) for tree in trees]


def test_single_table_gives_one_tree_without_edges() -> None:
    trees = find_spanning_trees(make_graph(), ["orders"])
    assert [(tree.root, tree.edges) for tree in trees] == [("orders", ())]


def test_path_gives_one_tree_rooted_at_the_first_table_by_name() -> None:
    trees = find_spanning_trees(make_graph(), ["orders", "customers", "order_items"])
    assert len(trees) == 1
    tree = trees[0]
    assert tree.root == "customers"
    assert [(e.parent_table, e.child_table) for e in tree.edges] == [
        ("customers", "orders"),
        ("orders", "order_items"),
    ]


def test_two_foreign_keys_between_the_same_tables_give_two_trees() -> None:
    trees = find_spanning_trees(make_two_key_graph(), ["orders", "customers"])
    assert edge_ids(trees) == [("last_fkey",), ("orders_customer_id_fkey",)]


def test_two_keys_between_two_tables_double_the_trees_of_a_larger_set() -> None:
    tables = ["orders", "customers", "order_items"]
    trees = find_spanning_trees(make_two_key_graph(), tables)
    # Keys: last_fkey and orders_customer_id_fkey (customers-orders) and the
    # order_items key; every tree needs the order_items key plus one of the two.
    assert len(trees) == 2
    assert all("order_items_order_id_fkey" in ids for ids in edge_ids(trees))


def test_every_tree_is_inner_with_one_edge_less_than_tables() -> None:
    tables = ["orders", "customers", "order_items", "products"]
    for tree in find_spanning_trees(make_two_key_graph(), tables):
        assert len(tree.edges) == len(tables) - 1
        assert {edge.join_type for edge in tree.edges} == {JoinType.INNER}
        assert set(tree.tables) == set(tables)


def test_two_runs_give_the_same_trees_in_the_same_order() -> None:
    tables = ["orders", "customers", "order_items"]
    graph = make_two_key_graph()
    assert find_spanning_trees(graph, tables) == find_spanning_trees(graph, tables)


def test_disconnected_set_is_rejected() -> None:
    with pytest.raises(JoinTreeError, match="not connected"):
        find_spanning_trees(make_graph(), ["customers", "products"])


def test_unknown_table_is_rejected() -> None:
    with pytest.raises(NodeNotFoundError):
        find_spanning_trees(make_graph(), ["customers", "invoices"])


@pytest.mark.parametrize("tables", [[], (), "orders"])
def test_empty_set_is_rejected(tables: object) -> None:
    with pytest.raises(JoinTreeError, match="at least one table"):
        find_spanning_trees(make_graph(), tables)  # type: ignore[arg-type]


def test_repeated_table_is_rejected() -> None:
    with pytest.raises(JoinTreeError, match="twice"):
        find_spanning_trees(make_graph(), ["orders", "orders"])


def test_foreign_key_without_edge_id_is_rejected() -> None:
    graph = make_unlinked_graph()
    graph.add_foreign_key("orders", "customer_id", "customers", "id", "a", "b")
    with pytest.raises(JoinTreeError, match="has no edge_id"):
        find_spanning_trees(graph, ["orders", "customers"])


def test_foreign_keys_within_lists_only_keys_inside_the_set() -> None:
    links = foreign_keys_within(make_two_key_graph(), ["orders", "customers"])
    assert links == [
        ForeignKeyLink("last_fkey", "customers", "orders"),
        ForeignKeyLink("orders_customer_id_fkey", "orders", "customers"),
    ]


def test_foreign_keys_within_a_single_table_is_empty() -> None:
    assert foreign_keys_within(make_graph(), ["order_items"]) == []


def test_foreign_keys_within_rejects_a_key_without_edge_id() -> None:
    graph = make_unlinked_graph()
    graph.add_foreign_key("orders", "customer_id", "customers", "id", "a", "b")
    with pytest.raises(JoinTreeError, match="has no edge_id"):
        foreign_keys_within(graph, ["orders", "customers"])


def test_foreign_keys_within_rejects_an_unknown_table() -> None:
    with pytest.raises(NodeNotFoundError):
        foreign_keys_within(make_graph(), ["orders", "invoices"])

"""Unit tests for every inner join tree of a graph (no database)."""

from collections import Counter

import pytest

from brutal_sql.flow import find_all_join_trees
from brutal_sql.graph import GraphError, JoinType
from brutal_sql.graph.test_join_tree import make_graph
from brutal_sql.graph.test_spanning_trees import make_two_key_graph


def test_one_table_trees_have_no_edges_one_per_table() -> None:
    trees = find_all_join_trees(make_graph(), 1)
    assert [(tree.root, tree.tables, tree.edges) for tree in trees] == [
        ("customers", ("customers",), ()),
        ("order_items", ("order_items",), ()),
        ("orders", ("orders",), ()),
        ("products", ("products",), ()),
    ]


def test_path_graph_counts_by_size() -> None:
    # customers <- orders <- order_items -> products: one tree per connected set.
    trees = find_all_join_trees(make_graph(), 4)
    assert Counter(len(tree.tables) for tree in trees) == {1: 4, 2: 3, 3: 2, 4: 1}


def test_two_keys_between_two_tables_give_extra_trees() -> None:
    trees = find_all_join_trees(make_two_key_graph(), 2)
    assert Counter(len(tree.tables) for tree in trees) == {1: 4, 2: 4}


def test_every_tree_is_inner() -> None:
    for tree in find_all_join_trees(make_two_key_graph(), 4):
        assert all(edge.join_type is JoinType.INNER for edge in tree.edges)


def test_trees_come_in_table_set_order() -> None:
    trees = find_all_join_trees(make_graph(), 4)
    sizes = [len(tree.tables) for tree in trees]
    assert sizes == sorted(sizes)


@pytest.mark.parametrize("bad_value", [0, -2, 1.5, "2", None])
def test_bad_max_tables_raises(bad_value: object) -> None:
    graph = make_graph()
    with pytest.raises(GraphError, match="max_tables"):
        find_all_join_trees(graph, bad_value)  # type: ignore[arg-type]

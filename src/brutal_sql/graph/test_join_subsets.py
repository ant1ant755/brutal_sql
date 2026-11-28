"""Tests for connected table sets on the hand-written shop graph (no database)."""

from collections import Counter

import pytest

from brutal_sql.graph import GraphError, find_connected_table_sets
from brutal_sql.graph.test_schema_graph import make_shop_graph, make_unlinked_graph


def sizes(sets: list[tuple[str, ...]]) -> dict[int, int]:
    return dict(Counter(len(tables) for tables in sets))


def test_shop_graph_counts_by_size() -> None:
    # customers <- orders <- order_items -> products: a path of four tables.
    sets = find_connected_table_sets(make_shop_graph(), 4)
    assert sizes(sets) == {1: 4, 2: 3, 3: 2, 4: 1}


def test_sets_are_ordered_by_size_then_names() -> None:
    sets = find_connected_table_sets(make_shop_graph(), 3)
    assert sets == [
        ("customers",),
        ("order_items",),
        ("orders",),
        ("products",),
        ("customers", "orders"),
        ("order_items", "orders"),
        ("order_items", "products"),
        ("customers", "order_items", "orders"),
        ("order_items", "orders", "products"),
    ]


def test_max_tables_two_returns_only_sizes_one_and_two() -> None:
    sets = find_connected_table_sets(make_shop_graph(), 2)
    assert set(sizes(sets)) == {1, 2}


def test_table_names_are_sorted_inside_each_set() -> None:
    for tables in find_connected_table_sets(make_shop_graph(), 4):
        assert list(tables) == sorted(tables)


def test_two_runs_give_the_same_order() -> None:
    graph = make_shop_graph()
    assert find_connected_table_sets(graph, 4) == find_connected_table_sets(graph, 4)


def test_unlinked_tables_only_appear_alone() -> None:
    sets = find_connected_table_sets(make_unlinked_graph(), 3)
    assert sets == [("customers",), ("order_items",), ("orders",), ("products",)]


def test_max_tables_larger_than_the_graph_is_fine() -> None:
    assert len(find_connected_table_sets(make_shop_graph(), 10)) == 10


def test_set_needing_an_outside_table_is_not_connected() -> None:
    sets = find_connected_table_sets(make_shop_graph(), 2)
    assert ("customers", "order_items") not in sets


@pytest.mark.parametrize("bad_value", [0, -1, 2.5, "3", True])
def test_bad_max_tables_raises(bad_value: object) -> None:
    with pytest.raises(GraphError, match="max_tables"):
        graph = make_shop_graph()
        find_connected_table_sets(graph, bad_value)  # type: ignore[arg-type]


def test_non_graph_raises() -> None:
    with pytest.raises(GraphError, match="not a Graph"):
        find_connected_table_sets("shop", 2)  # type: ignore[arg-type]

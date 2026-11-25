"""Traversal tests for the schema graph, on the hand-written orders schema."""

import pytest

from brutal_sql.graph.entity import Edge, EdgeType
from brutal_sql.graph.errors import GraphError, NodeNotFoundError
from brutal_sql.graph.schema_graph import JoinStep, count_backward_steps
from brutal_sql.graph.test_schema_graph import (
    add_last_order_key,
    conditions_in,
    make_shop_graph,
    make_unlinked_graph,
    tables_in,
)


def test_join_step_builds_join_condition() -> None:
    edge = Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)
    step = JoinStep("orders", edge)
    assert step.to_table == "customers"
    assert step.to_join_condition() == "orders.customer_id = customers.id"


def test_join_step_rejects_blank_table_and_non_edge() -> None:
    edge = Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)
    with pytest.raises(GraphError, match="from_table"):
        JoinStep(" ", edge)
    with pytest.raises(GraphError, match="not an Edge"):
        JoinStep("orders", "customers")


def test_neighbours_lists_forward_edges_before_backward_edges() -> None:
    steps = make_shop_graph().neighbours("orders")
    assert [step.edge.verb_label for step in steps] == ["placed by", "contains"]


def test_neighbours_forward_only_skips_backward_edges() -> None:
    assert make_shop_graph().neighbours("customers", forward_only=True) == []


def test_neighbours_rejects_unknown_table() -> None:
    with pytest.raises(NodeNotFoundError):
        make_shop_graph().neighbours("payments")


def test_join_options_lists_every_direct_join_between_two_tables() -> None:
    graph = make_shop_graph()
    add_last_order_key(graph)
    steps = graph.join_options("orders", "customers")
    assert [step.to_join_condition() for step in steps] == [
        "orders.customer_id = customers.id",
        "orders.id = customers.last_order_id",
    ]


def test_join_options_is_empty_for_tables_not_directly_joined() -> None:
    assert make_shop_graph().join_options("customers", "products") == []


def test_join_options_rejects_unknown_table() -> None:
    with pytest.raises(NodeNotFoundError):
        make_shop_graph().join_options("orders", "payments")


def test_walk_from_visits_tables_breadth_first() -> None:
    order = make_shop_graph().walk_from("order_items")
    assert order == ["order_items", "orders", "products", "customers"]


def test_walk_from_forward_only_stops_at_tables_without_foreign_keys() -> None:
    assert make_shop_graph().walk_from("customers", forward_only=True) == ["customers"]


def test_walk_from_rejects_unknown_table() -> None:
    with pytest.raises(NodeNotFoundError):
        make_shop_graph().walk_from("payments")


def test_find_all_join_paths_from_lists_every_path_shortest_first() -> None:
    paths = make_shop_graph().find_all_join_paths_from("products")
    assert [tables_in(path) for path in paths] == [
        ["products", "order_items"],
        ["products", "order_items", "orders"],
        ["products", "order_items", "orders", "customers"],
    ]


def test_find_all_join_paths_from_respects_max_joins() -> None:
    graph = make_shop_graph()
    paths = graph.find_all_join_paths_from("order_items", max_joins=1)
    assert [tables_in(path) for path in paths] == [
        ["order_items", "orders"],
        ["order_items", "products"],
    ]


@pytest.mark.parametrize("max_joins", [0, -1, 1.5, True])
def test_find_all_join_paths_from_rejects_invalid_max_joins(max_joins: object) -> None:
    with pytest.raises(GraphError, match="max_joins"):
        make_shop_graph().find_all_join_paths_from("orders", max_joins=max_joins)


def test_find_all_join_paths_from_unlinked_table_is_empty() -> None:
    assert make_unlinked_graph().find_all_join_paths_from("orders") == []


def test_find_all_join_paths_lists_each_foreign_key_as_its_own_path() -> None:
    graph = make_shop_graph()
    add_last_order_key(graph)
    paths = graph.find_all_join_paths("order_items", "customers")
    assert [conditions_in(path) for path in paths] == [
        ["order_items.order_id = orders.id", "orders.customer_id = customers.id"],
        ["order_items.order_id = orders.id", "orders.id = customers.last_order_id"],
    ]
    assert [count_backward_steps(path) for path in paths] == [0, 1]


def test_find_all_join_paths_uses_backward_edges_to_reach_customers() -> None:
    paths = make_shop_graph().find_all_join_paths("customers", "products")
    assert [tables_in(path) for path in paths] == [
        ["customers", "orders", "order_items", "products"]
    ]


def test_find_all_join_paths_forward_only_finds_no_path_backwards() -> None:
    graph = make_shop_graph()
    assert graph.find_all_join_paths("customers", "products", forward_only=True) == []


def test_find_all_join_paths_rejects_unknown_end_table() -> None:
    with pytest.raises(NodeNotFoundError):
        make_shop_graph().find_all_join_paths("orders", "payments")


def test_find_all_join_paths_rejects_same_start_and_end() -> None:
    with pytest.raises(GraphError, match="different tables"):
        make_shop_graph().find_all_join_paths("orders", "orders")


def test_count_backward_steps_counts_only_backward_edges() -> None:
    path = make_shop_graph().find_all_join_paths("products", "customers")[0]
    assert count_backward_steps(path) == 1


def test_count_backward_steps_of_empty_path_is_zero() -> None:
    assert count_backward_steps([]) == 0

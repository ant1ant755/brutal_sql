"""Tests for adding composite foreign keys to the schema graph."""

import pytest

from brutal_sql.graph import (
    AttributeNotFoundError,
    DuplicateEdgeError,
    EdgeType,
    EntityAttribute,
    EntityNode,
    Graph,
    GraphError,
    NodeNotFoundError,
)
from brutal_sql.graph.foreign_key_edges import (
    build_foreign_key_edges,
    edge_along,
    pair_foreign_key_columns,
)

KEY = ["order_id", "line_no"]


def node(name: str, columns: list[str]) -> EntityNode:
    return EntityNode(name, [EntityAttribute(column, column) for column in columns])


def make_lines_graph() -> Graph:
    return Graph(
        "lines",
        [node("order_lines", [*KEY, "sku"]), node("shipments", ["id", *KEY])],
    )


def add_ships(graph: Graph, source: object = KEY, target: object = KEY) -> tuple:
    return graph.add_composite_foreign_key(
        "shipments", source, "order_lines", target, "ships", "shipped by"
    )  # type: ignore[arg-type]


def test_composite_key_adds_one_edge_each_way_with_both_pairs() -> None:
    graph = make_lines_graph()
    forward, backward = add_ships(graph)
    assert graph.get_node("shipments").edges == [forward]
    assert graph.get_node("order_lines").edges == [backward]
    assert forward.edge_type == EdgeType.FORWARD
    assert forward.target_table == "order_lines"
    assert forward.column_pairs == (("order_id", "order_id"), ("line_no", "line_no"))
    assert backward.edge_type == EdgeType.BACKWARD
    assert backward.target_table == "shipments"
    assert backward.column_pairs == forward.column_pairs


def test_backward_edge_swaps_each_pair() -> None:
    graph = make_lines_graph()
    _, backward = add_ships(graph, ["order_id", "line_no"], ["order_id", "sku"])
    assert backward.column_pairs == (("order_id", "order_id"), ("sku", "line_no"))


def test_single_column_foreign_key_still_has_no_extra_pairs() -> None:
    graph = make_lines_graph()
    forward, backward = graph.add_foreign_key(
        "shipments", "order_id", "order_lines", "order_id", "ships", "shipped by"
    )
    assert forward.extra_column_pairs == () == backward.extra_column_pairs


@pytest.mark.parametrize(
    "source, target",
    [(KEY, ["order_id"]), (["order_id"], KEY), (KEY, [*KEY, "sku"])],
)
def test_column_counts_that_differ_raise(source: list, target: list) -> None:
    graph = make_lines_graph()
    with pytest.raises(GraphError, match="column counts differ"):
        add_ships(graph, source, target)
    assert graph.get_node("shipments").edges == []


@pytest.mark.parametrize(
    "source, target", [([], []), ("order_id", "order_id"), (None, KEY)]
)
def test_empty_or_non_list_columns_raise(source: object, target: object) -> None:
    with pytest.raises(GraphError):
        add_ships(make_lines_graph(), source, target)


def test_missing_column_on_either_side_raises_and_adds_nothing() -> None:
    graph = make_lines_graph()
    with pytest.raises(AttributeNotFoundError, match="ghost"):
        add_ships(graph, ["order_id", "ghost"], KEY)
    with pytest.raises(AttributeNotFoundError, match="ghost"):
        add_ships(graph, KEY, ["order_id", "ghost"])
    assert graph.get_node("shipments").edges == []
    assert graph.get_node("order_lines").edges == []


def test_missing_table_and_repeated_key_raise() -> None:
    graph = make_lines_graph()
    with pytest.raises(NodeNotFoundError):
        graph.add_composite_foreign_key("ghosts", KEY, "order_lines", KEY, "a", "b")
    add_ships(graph)
    with pytest.raises(DuplicateEdgeError):
        add_ships(graph)


def test_pair_foreign_key_columns_zips_in_order() -> None:
    assert pair_foreign_key_columns(("a", "b"), ["x", "y"]) == [("a", "x"), ("b", "y")]
    with pytest.raises(GraphError, match="column counts differ"):
        pair_foreign_key_columns(["a", "b"], ["x"])


def test_edge_along_needs_a_pair() -> None:
    edge = edge_along([("a", "x"), ("b", "y")], "t", "verb", EdgeType.FORWARD)
    assert edge.column_pairs == (("a", "x"), ("b", "y"))
    with pytest.raises(GraphError, match="at least one column pair"):
        edge_along([], "t", "verb", EdgeType.FORWARD)


def test_build_foreign_key_edges_returns_forward_then_backward() -> None:
    forward, backward = build_foreign_key_edges("s", [("a", "x")], "t", ("f", "b"))
    assert (forward.target_table, forward.verb_label) == ("t", "f")
    assert (backward.target_table, backward.column_pairs) == ("s", (("x", "a"),))
    with pytest.raises(GraphError):
        build_foreign_key_edges("s", [("a", " ")], "t", ("f", "b"))

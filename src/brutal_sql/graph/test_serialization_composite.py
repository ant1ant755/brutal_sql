"""Tests for composite foreign key edges in graph JSON."""

import json

import pytest

from brutal_sql.graph import (
    EntityAttribute,
    EntityNode,
    Graph,
    GraphError,
    graph_from_dict,
    graph_from_json,
    graph_to_dict,
)

KEY = ["order_id", "line_no"]


def make_lines_graph() -> Graph:
    lines = EntityNode("order_lines", [EntityAttribute(c, c) for c in KEY])
    shipments = EntityNode("shipments", [EntityAttribute(c, c) for c in ["id", *KEY]])
    graph = Graph("lines", [lines, shipments])
    graph.add_composite_foreign_key(
        "shipments", KEY, "order_lines", KEY, "ships", "shipped by"
    )
    return graph


def test_composite_edges_round_trip_with_both_pairs() -> None:
    original = make_lines_graph()
    restored = graph_from_json(original.to_json())
    for name in ["shipments", "order_lines"]:
        (edge,) = restored.get_node(name).edges
        assert edge == original.get_node(name).edges[0]
        assert edge.column_pairs == (("order_id", "order_id"), ("line_no", "line_no"))


def test_composite_edge_dict_lists_extra_pairs() -> None:
    data = graph_to_dict(make_lines_graph())
    edge = data["nodes"][1]["edges"][0]
    assert edge["source_field"] == "order_id"
    assert edge["extra_column_pairs"] == [["line_no", "line_no"]]
    assert json.loads(json.dumps(data)) == data


def test_json_without_extra_pairs_key_still_loads() -> None:
    data = graph_to_dict(make_lines_graph())
    for node in data["nodes"]:
        for edge in node["edges"]:
            del edge["extra_column_pairs"]
    restored = graph_from_dict(data)
    (edge,) = restored.get_node("shipments").edges
    assert edge.column_pairs == (("order_id", "order_id"),)


@pytest.mark.parametrize(
    "pairs",
    ["line_no", [["line_no"]], [["line_no", "line_no", "x"]], ["line_no"], [[1, 2]]],
)
def test_malformed_extra_pairs_raise(pairs: object) -> None:
    data = graph_to_dict(make_lines_graph())
    data["nodes"][1]["edges"][0]["extra_column_pairs"] = pairs
    with pytest.raises(GraphError):
        graph_from_dict(data)


def test_extra_pair_naming_a_missing_target_column_raises() -> None:
    data = graph_to_dict(make_lines_graph())
    data["nodes"][1]["edges"][0]["extra_column_pairs"] = [["line_no", "ghost"]]
    with pytest.raises(GraphError, match="ghost"):
        graph_from_dict(data)

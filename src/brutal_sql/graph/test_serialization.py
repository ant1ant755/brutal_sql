"""Tests for converting a schema graph to and from JSON."""

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
    graph_to_json,
)


def make_graph() -> Graph:
    customers = EntityNode(
        "customers", [EntityAttribute("id", "id"), EntityAttribute("nm", "name")]
    )
    orders = EntityNode(
        "orders", [EntityAttribute("id", "id"), EntityAttribute("cid", "customer id")]
    )
    graph = Graph("shop", [customers, orders])
    graph.add_foreign_key("orders", "cid", "customers", "id", "placed by", "places")
    return graph


def describe(graph: Graph) -> list[tuple[object, ...]]:
    return [
        (node.name, tuple(node.attributes), tuple(node.edges)) for node in graph.nodes
    ]


def test_json_round_trip_keeps_nodes_attributes_and_edges() -> None:
    original = make_graph()
    restored = graph_from_json(graph_to_json(original))
    assert restored.schema_name == "shop"
    assert describe(restored) == describe(original)


def test_graph_methods_round_trip() -> None:
    original = make_graph()
    assert describe(Graph.from_json(original.to_json())) == describe(original)


def test_graph_to_dict_is_plain_json_data() -> None:
    data = graph_to_dict(make_graph())
    assert json.loads(json.dumps(data)) == data
    assert data["nodes"][1]["edges"][0]["edge_type"] == "forward"


def broken_data(path: list[object], value: object) -> dict[str, object]:
    data = graph_to_dict(make_graph())
    target: object = data
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    if value is KeyError:
        del target[path[-1]]  # type: ignore[attr-defined]
    else:
        target[path[-1]] = value  # type: ignore[index]
    return data


@pytest.mark.parametrize(
    "path, value",
    [
        (["format_version"], 99),
        (["schema_name"], KeyError),
        (["nodes"], "not a list of nodes"),
        (["nodes", 0, "attributes"], KeyError),
        (["nodes", 1, "edges", 0, "edge_type"], "sideways"),
        (["nodes", 1, "edges", 0, "target_table"], "ghosts"),
    ],
)
def test_graph_from_dict_rejects_malformed_data(
    path: list[object], value: object
) -> None:
    with pytest.raises(GraphError):
        graph_from_dict(broken_data(path, value))


@pytest.mark.parametrize("data", [None, [], "graph"])
def test_graph_from_dict_rejects_non_dict(data: object) -> None:
    with pytest.raises(GraphError):
        graph_from_dict(data)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["{not json", "", b"{}", None])
def test_graph_from_json_rejects_invalid_text(text: object) -> None:
    with pytest.raises(GraphError):
        graph_from_json(text)  # type: ignore[arg-type]


def test_graph_from_json_rejects_unknown_version() -> None:
    with pytest.raises(GraphError):
        Graph.from_json('{"format_version": 2, "schema_name": "s", "nodes": []}')

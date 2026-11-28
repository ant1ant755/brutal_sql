"""Tests that graph JSON keeps each edge's edge_id and nullable."""

from typing import Any

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
    address = EntityNode("address", [EntityAttribute("id", "id")])
    complaints = EntityNode(
        "complaints",
        [EntityAttribute("id", "id"), EntityAttribute("address_id", "address id")],
    )
    graph = Graph("shop", [address, complaints])
    graph.add_foreign_key(
        "complaints",
        "address_id",
        "address",
        "id",
        "about",
        "has",
        edge_id="complaints_address_id_fkey",
        nullable=True,
    )
    return graph


def edge_identities(graph: Graph) -> list[tuple[str, str | None, bool]]:
    return [
        (node.name, edge.edge_id, edge.nullable)
        for node in graph.nodes
        for edge in node.edges
    ]


def test_json_round_trip_keeps_edge_id_and_nullable() -> None:
    restored = graph_from_json(graph_to_json(make_graph()))
    assert edge_identities(restored) == [
        ("address", "complaints_address_id_fkey", True),
        ("complaints", "complaints_address_id_fkey", True),
    ]


def test_graph_to_dict_writes_edge_id_and_nullable() -> None:
    edge = graph_to_dict(make_graph())["nodes"][1]["edges"][0]
    assert edge["edge_id"] == "complaints_address_id_fkey"
    assert edge["nullable"] is True


def test_round_trip_keeps_missing_edge_id_as_none() -> None:
    graph = make_graph()
    graph.remove_foreign_key("complaints", "address_id", "address", "id")
    graph.add_foreign_key("complaints", "address_id", "address", "id", "a", "b")
    assert edge_identities(Graph.from_json(graph.to_json())) == [
        ("address", None, False),
        ("complaints", None, False),
    ]


def edge_data_without(key: str) -> dict[str, Any]:
    data = graph_to_dict(make_graph())
    del data["nodes"][1]["edges"][0][key]
    return data


@pytest.mark.parametrize("key", ["edge_id", "nullable"])
def test_graph_from_dict_rejects_edge_missing_identity(key: str) -> None:
    with pytest.raises(GraphError, match=f"missing '{key}'"):
        graph_from_dict(edge_data_without(key))


@pytest.mark.parametrize(
    "key, value",
    [("nullable", "true"), ("nullable", 1), ("edge_id", ""), ("edge_id", 5)],
)
def test_graph_from_dict_rejects_bad_identity_values(key: str, value: object) -> None:
    data = graph_to_dict(make_graph())
    data["nodes"][1]["edges"][0][key] = value
    with pytest.raises(GraphError, match=key):
        graph_from_dict(data)

"""Tests that table types and role names survive graph JSON serialization."""

import pytest

from brutal_sql.graph import (
    EdgeType,
    Graph,
    GraphError,
    TableType,
    apply_annotations,
    graph_from_dict,
    graph_to_dict,
)
from brutal_sql.graph.test_annotations_apply import complete_annotations
from brutal_sql.graph.test_annotations_draft import make_orders_graph


def annotated_graph() -> Graph:
    return apply_annotations(make_orders_graph(), complete_annotations())


def test_table_type_and_role_name_round_trip_through_json() -> None:
    restored = Graph.from_json(annotated_graph().to_json())
    assert restored.get_node("address").table_type is TableType.DIMENSION
    edge = restored.get_node("orders").find_edge(
        EdgeType.FORWARD, "billing_address_id", "address", "id"
    )
    assert (edge.verb_label, edge.role_name) == ("billed to", "billing")


def test_unannotated_graph_writes_null_type_and_role_name() -> None:
    data = graph_to_dict(make_orders_graph())
    assert {node["table_type"] for node in data["nodes"]} == {None}
    roles = {edge["role_name"] for node in data["nodes"] for edge in node["edges"]}
    assert roles == {None}


def test_graph_data_without_annotation_keys_still_loads() -> None:
    data = graph_to_dict(annotated_graph())
    for node in data["nodes"]:
        del node["table_type"]
        for edge in node["edges"]:
            del edge["role_name"]
    graph = graph_from_dict(data)
    assert {node.table_type for node in graph.nodes} == {None}
    assert {edge.role_name for node in graph.nodes for edge in node.edges} == {None}


@pytest.mark.parametrize("bad_type", ["fact", 5])
def test_graph_data_with_unknown_table_type_is_rejected(bad_type: object) -> None:
    data = graph_to_dict(make_orders_graph())
    data["nodes"][0]["table_type"] = bad_type
    with pytest.raises(GraphError, match="unknown table_type"):
        graph_from_dict(data)


def test_graph_data_with_blank_role_name_is_rejected() -> None:
    data = graph_to_dict(make_orders_graph())
    data["nodes"][2]["edges"][0]["role_name"] = ""
    with pytest.raises(GraphError, match="role_name"):
        graph_from_dict(data)

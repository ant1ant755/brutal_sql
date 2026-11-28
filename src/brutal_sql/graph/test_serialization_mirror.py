"""Tests that mirror tables and their edges survive graph JSON serialization."""

import json
from typing import Any

import pytest

from brutal_sql.graph import (
    EdgeType,
    EntityAttribute,
    EntityNode,
    Graph,
    GraphError,
    MirrorSource,
    RowFilter,
    graph_from_dict,
    graph_from_json,
    graph_to_dict,
)


def staff_graph() -> Graph:
    employee = EntityNode(
        "employee",
        [EntityAttribute(name, name) for name in ("id", "manager_id", "name")],
    )
    source = MirrorSource(
        "employee", "manager_id", "id", (("id", "id"), ("name", "name"))
    )
    managers = EntityNode(
        "managers",
        [EntityAttribute("id", "id"), EntityAttribute("name", "name")],
        mirror_of=source,
    )
    graph = Graph("staff", [employee, managers])
    graph.add_foreign_key(
        "employee", "manager_id", "managers", "id", "references", "referenced by"
    )
    return graph


def staff_dict() -> dict[str, Any]:
    return graph_to_dict(staff_graph())


def test_mirror_and_edges_round_trip_through_json() -> None:
    restored = Graph.from_json(staff_graph().to_json())
    managers = restored.get_node("managers")
    assert managers.mirror_of == staff_graph().get_node("managers").mirror_of
    assert managers.mirror_of.row_filter == RowFilter.ONLY_REFERENCED_ROWS
    assert managers.mirror_of.column_mapping == (("id", "id"), ("name", "name"))
    assert restored.get_node("employee").mirror_of is None
    employee = restored.get_node("employee")
    assert employee.find_edge(EdgeType.FORWARD, "manager_id", "managers", "id")
    assert managers.find_edge(EdgeType.BACKWARD, "id", "employee", "manager_id")


def test_mirror_dict_is_plain_json_data() -> None:
    data = staff_dict()
    assert json.loads(json.dumps(data)) == data
    assert data["nodes"][0]["mirror_of"] is None
    assert data["nodes"][1]["mirror_of"]["physical_table"] == "employee"
    assert data["nodes"][1]["mirror_of"]["row_filter"] == "only_referenced_rows"


def test_node_without_mirror_key_loads_as_ordinary_node() -> None:
    data = staff_dict()
    data["nodes"] = data["nodes"][:1]
    data["nodes"][0]["edges"] = []
    del data["nodes"][0]["mirror_of"]
    assert graph_from_dict(data).get_node("employee").mirror_of is None


def test_unknown_row_filter_is_rejected() -> None:
    data = staff_dict()
    data["nodes"][1]["mirror_of"]["row_filter"] = "every_row"
    with pytest.raises(GraphError, match="row_filter"):
        graph_from_dict(data)


@pytest.mark.parametrize(
    "field, value",
    [
        ("column_mapping", ["idid"]),
        ("column_mapping", [["id"]]),
        ("column_mapping", []),
        ("physical_table", "nowhere"),
    ],
)
def test_malformed_mirror_is_rejected(field: str, value: object) -> None:
    data = staff_dict()
    data["nodes"][1]["mirror_of"][field] = value
    with pytest.raises(GraphError):
        graph_from_dict(data)


def test_mirror_missing_a_key_is_rejected() -> None:
    data = staff_dict()
    del data["nodes"][1]["mirror_of"]["referencing_column"]
    with pytest.raises(GraphError, match="malformed"):
        graph_from_json(json.dumps(data))

"""Tests for mirror table sources (graph-only copies of self-referencing tables)."""

import pytest

from brutal_sql.graph import (
    AttributeNotFoundError,
    EntityAttribute,
    EntityNode,
    Graph,
    GraphError,
    MirrorSource,
    NodeNotFoundError,
    RowFilter,
)
from brutal_sql.graph.mirror import require_mirror_columns

MAPPING = (("id", "id"), ("name", "name"))


def manager_source(**changes: object) -> MirrorSource:
    values: dict[str, object] = {
        "physical_table": "employee",
        "referencing_column": "manager_id",
        "referenced_column": "id",
        "column_mapping": MAPPING,
        "row_filter": RowFilter.ONLY_REFERENCED_ROWS,
    }
    values.update(changes)
    return MirrorSource(**values)  # type: ignore[arg-type]


def employee_node() -> EntityNode:
    return EntityNode(
        "employee",
        [EntityAttribute(name, name) for name in ("id", "manager_id", "name")],
    )


def managers_node(source: MirrorSource | None = None) -> EntityNode:
    attributes = [EntityAttribute("id", "id"), EntityAttribute("name", "name")]
    return EntityNode("managers", attributes, mirror_of=source or manager_source())


def test_mirror_source_keeps_its_fields() -> None:
    source = manager_source()
    assert source.physical_table == "employee"
    assert source.mirror_columns == ["id", "name"]
    assert source.physical_columns == ["id", "name"]
    assert source.row_filter == RowFilter.ONLY_REFERENCED_ROWS


def test_row_filter_defaults_to_only_referenced_rows() -> None:
    source = MirrorSource("employee", "manager_id", "id", MAPPING)
    assert source.row_filter == RowFilter.ONLY_REFERENCED_ROWS


def test_derived_table_sql_selects_distinct_referenced_rows() -> None:
    assert manager_source().to_derived_table_sql() == (
        "SELECT DISTINCT m.id, m.name FROM employee AS e "
        "JOIN employee AS m ON e.manager_id = m.id"
    )


def test_derived_table_sql_aliases_renamed_columns() -> None:
    source = manager_source(column_mapping=(("boss_id", "id"),))
    assert "m.id AS boss_id" in source.to_derived_table_sql()


@pytest.mark.parametrize(
    "changes",
    [
        {"physical_table": " "},
        {"referencing_column": ""},
        {"referenced_column": None},
        {"column_mapping": ()},
        {"column_mapping": [("id", "id")]},
        {"column_mapping": (("id",),)},
        {"column_mapping": (("id", ""),)},
        {"column_mapping": (("id", "id"), ("id", "name"))},
        {"row_filter": "only_referenced_rows"},
    ],
)
def test_mirror_source_rejects_invalid_fields(changes: dict[str, object]) -> None:
    with pytest.raises(GraphError):
        manager_source(**changes)


def test_require_mirror_columns_accepts_complete_table() -> None:
    require_mirror_columns(manager_source(), ["id", "manager_id", "name"])


@pytest.mark.parametrize("missing", ["id", "manager_id", "name"])
def test_require_mirror_columns_rejects_missing_column(missing: str) -> None:
    columns = [name for name in ("id", "manager_id", "name") if name != missing]
    with pytest.raises(AttributeNotFoundError, match=missing):
        require_mirror_columns(manager_source(), columns)


def test_entity_node_marks_mirror() -> None:
    assert managers_node().is_mirror
    assert managers_node().mirror_of == manager_source()
    assert not employee_node().is_mirror
    assert employee_node().mirror_of is None


def test_entity_node_rejects_mirror_of_wrong_type() -> None:
    with pytest.raises(GraphError, match="MirrorSource"):
        EntityNode("managers", [EntityAttribute("id", "id")], mirror_of="employee")


def test_entity_node_rejects_mapping_not_matching_attributes() -> None:
    with pytest.raises(GraphError, match="does not match"):
        EntityNode(
            "managers", [EntityAttribute("id", "id")], mirror_of=manager_source()
        )


def test_graph_accepts_mirror_of_existing_table() -> None:
    graph = Graph("staff", [employee_node(), managers_node()])
    assert graph.get_node("managers").is_mirror


def test_graph_add_node_accepts_mirror() -> None:
    graph = Graph("staff", [employee_node()])
    graph.add_node(managers_node())
    assert [node.name for node in graph.nodes] == ["employee", "managers"]


def test_graph_rejects_mirror_of_missing_table() -> None:
    with pytest.raises(NodeNotFoundError, match="employee"):
        Graph("staff", [managers_node()])


def test_graph_rejects_mirror_of_table_missing_column() -> None:
    employee = EntityNode("employee", [EntityAttribute("id", "id")])
    graph = Graph("staff", [employee])
    with pytest.raises(AttributeNotFoundError):
        graph.add_node(managers_node())

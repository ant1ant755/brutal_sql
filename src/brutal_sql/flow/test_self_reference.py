"""Tests for turning self-referencing tables into mirror nodes (no database)."""

import logging

import pytest

from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.schema_to_graph import (
    build_entity_node,
    convert_tables_to_graph,
    without_self_references,
)
from brutal_sql.flow.self_reference import (
    add_mirror_tables,
    build_mirror_node,
    is_self_referencing,
    mirror_column_names,
    mirror_table_name,
)
from brutal_sql.graph import EdgeNotFoundError, EdgeType, Graph, RowFilter

SCHEMA = "staff"
MANAGER_KEY = ForeignKeyMetadata(("manager_id",), SCHEMA, "employee", ("id",))
DEPARTMENT_KEY = ForeignKeyMetadata(("department_id",), SCHEMA, "department", ("id",))


def column(name: str, comment: str | None = None) -> ColumnMetadata:
    return ColumnMetadata(name, "INTEGER", comment=comment)


def employee(*keys: ForeignKeyMetadata, extra: tuple[str, ...] = ()) -> TableMetadata:
    columns = (
        column("id"),
        column("manager_id"),
        column("name", "employee name"),
        column("department_id"),
        *(column(name) for name in extra),
    )
    return TableMetadata("employee", columns, ("id",), (), keys)


def staff_tables() -> list[TableMetadata]:
    department = TableMetadata("department", (column("id"), column("title")), ("id",))
    return [department, employee(MANAGER_KEY, DEPARTMENT_KEY)]


def edge_set(graph: Graph, edge_type: EdgeType) -> set[tuple[str, str, str, str]]:
    return {
        (node.name, edge.source_field, edge.target_table, edge.target_table_field)
        for node in graph.nodes
        for edge in node.edges
        if edge.edge_type == edge_type
    }


@pytest.mark.parametrize(
    "column_name, expected",
    [
        ("manager_id", "managers"),
        ("mentor_ID", "mentors"),
        ("parents_id", "parents"),
        (" reports_to ", "reports_tos"),
    ],
)
def test_mirror_table_name_from_column(column_name: str, expected: str) -> None:
    assert mirror_table_name(column_name) == expected


@pytest.mark.parametrize("bad", ["", "  ", None])
def test_mirror_table_name_rejects_blank(bad: object) -> None:
    with pytest.raises(ProcessingError):
        mirror_table_name(bad)  # type: ignore[arg-type]


def test_is_self_referencing_for_key_to_own_table() -> None:
    assert is_self_referencing(employee(), MANAGER_KEY, SCHEMA)


@pytest.mark.parametrize(
    "key",
    [
        DEPARTMENT_KEY,
        ForeignKeyMetadata(("manager_id",), "hr", "employee", ("id",)),
        ForeignKeyMetadata(("a", "b"), SCHEMA, "employee", ("id", "name")),
    ],
)
def test_is_self_referencing_false_for_other_keys(key: ForeignKeyMetadata) -> None:
    assert not is_self_referencing(employee(), key, SCHEMA)


def test_mirror_columns_drop_primary_key_and_rename_foreign_key() -> None:
    names = mirror_column_names(employee(), MANAGER_KEY)
    assert names == ["id", "name", "department_id"]


def test_build_mirror_node_maps_every_column_to_employee() -> None:
    mirror = build_mirror_node(employee(), MANAGER_KEY)
    assert mirror.name == "managers"
    assert [attribute.name for attribute in mirror.attributes] == [
        "id",
        "name",
        "department_id",
    ]
    assert mirror.attributes[1].readable_name == "employee name"
    source = mirror.mirror_of
    assert source.physical_table == "employee"
    assert source.column_mapping == (
        ("id", "id"),
        ("name", "name"),
        ("department_id", "department_id"),
    )
    assert source.referencing_column == "manager_id"
    assert source.row_filter == RowFilter.ONLY_REFERENCED_ROWS


@pytest.mark.parametrize(
    "key",
    [
        DEPARTMENT_KEY,
        ForeignKeyMetadata(("a", "b"), SCHEMA, "employee", ("id", "name")),
    ],
)
def test_build_mirror_node_rejects_other_keys(key: ForeignKeyMetadata) -> None:
    with pytest.raises(ProcessingError, match="self reference"):
        build_mirror_node(employee(), key)


def test_graph_has_one_extra_node_for_self_referencing_table() -> None:
    tables = staff_tables()
    graph = convert_tables_to_graph(SCHEMA, tables)
    assert len(graph.nodes) == len(tables) + 1
    assert sorted(node.name for node in graph.nodes) == [
        "department",
        "employee",
        "managers",
    ]


def test_original_table_is_not_modified() -> None:
    graph = convert_tables_to_graph(SCHEMA, staff_tables())
    original = graph.get_node("employee")
    assert [attribute.name for attribute in original.attributes] == [
        "id",
        "manager_id",
        "name",
        "department_id",
    ]
    assert not original.is_mirror


def test_mirror_edges_replace_the_self_loop() -> None:
    graph = convert_tables_to_graph(SCHEMA, staff_tables())
    assert edge_set(graph, EdgeType.FORWARD) == {
        ("employee", "manager_id", "managers", "id"),
        ("employee", "department_id", "department", "id"),
    }
    assert edge_set(graph, EdgeType.BACKWARD) == {
        ("managers", "id", "employee", "manager_id"),
        ("department", "id", "employee", "department_id"),
    }
    employee_node = graph.get_node("employee")
    assert all(edge.target_table != "employee" for edge in employee_node.edges)
    with pytest.raises(EdgeNotFoundError):
        employee_node.find_edge(EdgeType.FORWARD, "manager_id", "employee", "id")


def test_conversion_does_not_warn_about_self_join(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        convert_tables_to_graph(SCHEMA, staff_tables())
    assert "self join" not in caplog.text


def test_two_self_referencing_keys_give_two_mirrors() -> None:
    mentor_key = ForeignKeyMetadata(("mentor_id",), SCHEMA, "employee", ("id",))
    table = employee(MANAGER_KEY, mentor_key, extra=("mentor_id",))
    graph = Graph(SCHEMA, [build_entity_node(table)])
    assert add_mirror_tables(graph, table) == 2
    assert [node.name for node in graph.nodes] == ["employee", "managers", "mentors"]


def test_table_without_self_reference_adds_no_mirror() -> None:
    table = employee()
    graph = Graph(SCHEMA, [build_entity_node(table)])
    assert add_mirror_tables(graph, table) == 0
    assert len(graph.nodes) == 1


def test_mirror_name_clash_raises() -> None:
    clash = TableMetadata("managers", (column("id"),), ("id",))
    with pytest.raises(ProcessingError, match="already exists"):
        convert_tables_to_graph(SCHEMA, [*staff_tables(), clash])


def test_without_self_references_keeps_other_keys() -> None:
    table = without_self_references(employee(MANAGER_KEY, DEPARTMENT_KEY), SCHEMA)
    assert table.foreign_keys == (DEPARTMENT_KEY,)
    assert table.columns == employee().columns


def test_mirror_column_names_rejects_key_to_other_table() -> None:
    with pytest.raises(ProcessingError, match="self reference"):
        mirror_column_names(employee(), DEPARTMENT_KEY)


def test_without_self_references_keeps_same_name_table_in_other_schema() -> None:
    other_schema_key = ForeignKeyMetadata(("manager_id",), "hr", "employee", ("id",))
    table = without_self_references(employee(other_schema_key), SCHEMA)
    assert table.foreign_keys == (other_schema_key,)

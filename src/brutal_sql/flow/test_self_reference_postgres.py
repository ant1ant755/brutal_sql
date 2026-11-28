"""Definition of done for ANT-9, against the Docker Compose Postgres.

Never skipped: start the database with `docker compose up -d`.
"""

import pytest
from sqlalchemy import create_engine, text

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow.fetch_schema_graph import fetch_schema_graph
from brutal_sql.graph import EdgeType, Graph, RowFilter

pytestmark = pytest.mark.postgres

LIST_RELATIONS = text(
    "SELECT table_name, table_type FROM information_schema.tables "
    "WHERE table_schema = :schema ORDER BY table_name"
)


def list_relations(settings: ConnectionSettings) -> list[tuple[str, str]]:
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.connect() as connection:
            rows = connection.execute(LIST_RELATIONS, {"schema": settings.schema_name})
            return [tuple(row) for row in rows]
    finally:
        engine.dispose()


def mirror_rows(settings: ConnectionSettings, graph: Graph) -> list[tuple[object, ...]]:
    select = graph.get_node("managers").mirror_of.to_derived_table_sql()
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f"SET search_path TO {settings.schema_name}")
            rows = connection.exec_driver_sql(f"{select} ORDER BY id")
            return [tuple(row) for row in rows]
    finally:
        engine.dispose()


def test_staff_graph_has_mirror_with_edges(staff_schema: ConnectionSettings) -> None:
    graph = fetch_schema_graph(staff_schema)
    names = sorted(node.name for node in graph.nodes)
    assert names == ["department", "employee", "managers"]
    employee = graph.get_node("employee")
    managers = graph.get_node("managers")
    assert [a.name for a in employee.attributes] == [
        "id",
        "manager_id",
        "name",
        "department_id",
    ]
    assert [a.name for a in managers.attributes] == ["id", "name", "department_id"]
    assert employee.find_edge(EdgeType.FORWARD, "manager_id", "managers", "id")
    assert managers.find_edge(EdgeType.BACKWARD, "id", "employee", "manager_id")
    assert all(edge.target_table != "employee" for edge in employee.edges)


def test_staff_mirror_maps_back_to_employee(staff_schema: ConnectionSettings) -> None:
    source = fetch_schema_graph(staff_schema).get_node("managers").mirror_of
    assert source.physical_table == "employee"
    assert dict(source.column_mapping) == {
        "id": "id",
        "name": "name",
        "department_id": "department_id",
    }
    assert source.row_filter == RowFilter.ONLY_REFERENCED_ROWS


def test_mirror_rows_are_only_referenced_employees(
    staff_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(staff_schema)
    rows = mirror_rows(staff_schema, graph)
    assert [(row[0], row[1]) for row in rows] == [(1, "alice"), (2, "bob")]


def test_mirror_round_trips_through_json(staff_schema: ConnectionSettings) -> None:
    graph = fetch_schema_graph(staff_schema)
    restored = Graph.from_json(graph.to_json())
    assert restored.get_node("managers").mirror_of == (
        graph.get_node("managers").mirror_of
    )
    assert restored.get_node("employee").edges == graph.get_node("employee").edges


def test_building_graph_creates_no_table_or_view(
    staff_schema: ConnectionSettings,
) -> None:
    before = list_relations(staff_schema)
    fetch_schema_graph(staff_schema)
    after = list_relations(staff_schema)
    assert after == before
    assert after == [("department", "BASE TABLE"), ("employee", "BASE TABLE")]

"""Definition of done for ANT-10, against the Docker Compose Postgres.

shipments(order_id, line_no) references order_lines(order_id, line_no).
Never skipped: start the database with `docker compose up -d`.
"""

import pytest
from sqlalchemy import create_engine

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow.fetch_schema_graph import fetch_schema_graph
from brutal_sql.graph import EdgeType, Graph, JoinStep

pytestmark = pytest.mark.postgres

BOTH_PAIRS = (("order_id", "order_id"), ("line_no", "line_no"))
CONDITION = (
    "shipments.order_id = order_lines.order_id"
    " AND shipments.line_no = order_lines.line_no"
)


def run_join(settings: ConnectionSettings, condition: str) -> list[tuple[object, ...]]:
    sql = (
        "SELECT shipments.id, order_lines.sku FROM shipments "
        f"JOIN order_lines ON {condition} ORDER BY order_lines.sku"
    )
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f"SET search_path TO {settings.schema_name}")
            return [tuple(row) for row in connection.exec_driver_sql(sql)]
    finally:
        engine.dispose()


def test_composite_key_gives_one_edge_each_way(
    lines_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(lines_schema)
    (forward,) = graph.get_node("shipments").edges
    (backward,) = graph.get_node("order_lines").edges
    assert (forward.edge_type, forward.target_table) == (
        EdgeType.FORWARD,
        "order_lines",
    )
    assert (backward.edge_type, backward.target_table) == (
        EdgeType.BACKWARD,
        "shipments",
    )
    assert forward.column_pairs == BOTH_PAIRS
    assert backward.column_pairs == BOTH_PAIRS


def test_join_condition_has_both_pairs(lines_schema: ConnectionSettings) -> None:
    graph = fetch_schema_graph(lines_schema)
    (step,) = graph.join_options("shipments", "order_lines")
    assert step.to_join_condition() == CONDITION
    (back,) = graph.join_options("order_lines", "shipments")
    assert back.to_join_condition() == (
        "order_lines.order_id = shipments.order_id"
        " AND order_lines.line_no = shipments.line_no"
    )


def test_join_condition_matches_only_the_shipped_line(
    lines_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(lines_schema)
    step = JoinStep("shipments", graph.get_node("shipments").edges[0])
    assert run_join(lines_schema, step.to_join_condition()) == [(1, "ink")]
    first_pair_only = "shipments.order_id = order_lines.order_id"
    assert len(run_join(lines_schema, first_pair_only)) == 3


def test_composite_edges_round_trip_through_json(
    lines_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(lines_schema)
    restored = Graph.from_json(graph.to_json())
    for name in ["shipments", "order_lines"]:
        assert restored.get_node(name).edges == graph.get_node(name).edges
        assert restored.get_node(name).edges[0].column_pairs == BOTH_PAIRS

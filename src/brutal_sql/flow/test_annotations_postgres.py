"""Definition of done for ANT-12, against the Docker Compose Postgres.

Never skipped: start the database with `docker compose up -d`.
"""

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow import BACKWARD_VERB, FORWARD_VERB
from brutal_sql.flow.fetch_schema_graph import fetch_schema_graph
from brutal_sql.graph import TODO_MARKER, EdgeType, draft_annotations

pytestmark = pytest.mark.postgres

SHOP_EDGES = {
    "orders_customer_id_fkey": ("orders", "customer"),
    "order_items_order_id_fkey": ("order_items", "orders"),
    "order_items_product_id_fkey": ("order_items", "products"),
}


def test_draft_for_shop_lists_every_table_and_edge_id_as_todo(
    shop_schema: ConnectionSettings,
) -> None:
    draft = draft_annotations(fetch_schema_graph(shop_schema))
    assert draft["schema_name"] == "ant8_shop"
    assert draft["tables"] == {
        name: {"type": TODO_MARKER}
        for name in ("customer", "products", "orders", "order_items")
    }
    assert set(draft["edges"]) == set(SHOP_EDGES)
    for edge_id, (from_table, to_table) in SHOP_EDGES.items():
        assert draft["edges"][edge_id] == {
            "from_table": from_table,
            "to_table": to_table,
            "verb_forward": TODO_MARKER,
            "verb_backward": TODO_MARKER,
            "role_name": TODO_MARKER,
        }


def test_shop_graph_without_annotations_keeps_placeholders(
    shop_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(shop_schema)
    assert {node.table_type for node in graph.nodes} == {None}
    for node in graph.nodes:
        for edge in node.edges:
            expected = (
                FORWARD_VERB if edge.edge_type == EdgeType.FORWARD else (BACKWARD_VERB)
            )
            assert (edge.verb_label, edge.role_name) == (expected, None)

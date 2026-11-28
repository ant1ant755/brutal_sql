"""Definition of done for ANT-13, against the Docker Compose Postgres.

Never skipped: start the database with `docker compose up -d`.
"""

import logging
from typing import Any

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.errors import ProcessingError
from brutal_sql.flow import build_annotated_graph, fetch_schema_graph
from brutal_sql.graph import TableType, draft_annotations

pytestmark = pytest.mark.postgres

SHOP_VERBS = {
    "orders_customer_id_fkey": ("placed by", "places"),
    "order_items_order_id_fkey": ("part of", "contains"),
    "order_items_product_id_fkey": ("is for", "ordered as"),
}


def shop_annotations(settings: ConnectionSettings) -> dict[str, Any]:
    annotations = draft_annotations(fetch_schema_graph(settings))
    for entry in annotations["tables"].values():
        entry["type"] = "entity"
    annotations["tables"]["products"]["type"] = "dimension"
    for edge_id, (forward, backward) in SHOP_VERBS.items():
        annotations["edges"][edge_id].update(
            verb_forward=forward, verb_backward=backward, role_name=None
        )
    return annotations


def test_fully_annotated_shop_graph_passes(shop_schema: ConnectionSettings) -> None:
    graph = build_annotated_graph(shop_schema, shop_annotations(shop_schema))
    assert graph.get_node("products").table_type is TableType.DIMENSION
    assert {edge.verb_label for edge in graph.get_node("orders").edges} == {
        "placed by",
        "contains",
    }


def test_incomplete_shop_ontology_fails_without_leaking(
    shop_schema: ConnectionSettings, caplog: pytest.LogCaptureFixture
) -> None:
    annotations = shop_annotations(shop_schema)
    annotations["tables"]["orders"]["type"] = "TODO"
    annotations["edges"]["orders_customer_id_fkey"]["verb_backward"] = "TODO"
    with caplog.at_level(logging.DEBUG), pytest.raises(ProcessingError) as caught:
        build_annotated_graph(shop_schema, annotations)
    # The local username may be part of the database name (shown as
    # host:port/database) or of the package name (in logger names), so check
    # log messages, not formatted log lines, with the allowed location removed.
    allowed = shop_schema.describe_database()
    texts = [str(caught.value), repr(caught.value), str(caught.value.__cause__)]
    texts = [text.replace(allowed, "") for text in [*texts, *caplog.messages]]
    secrets = [str(shop_schema.username), str(shop_schema.password)]
    leaked = any(secret in text for secret in secrets for text in texts)
    assert not leaked, "error text or logs leak a database username or password"
    cause_text = str(caught.value.__cause__)
    cause_leaks = any(secret in cause_text for secret in secrets)
    assert not cause_leaks, "ontology error text leaks a database username or password"
    assert "table 'orders' has no table type" in str(caught.value)
    assert "'orders_customer_id_fkey' (customer -> orders) has no backward verb" in str(
        caught.value
    )

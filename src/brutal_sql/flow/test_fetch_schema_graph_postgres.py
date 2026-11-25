"""Definition of done for ANT-8, against the Docker Compose Postgres.

Never skipped: start the database with `docker compose up -d`.
"""

import dataclasses
import logging

import pytest

from brutal_sql.db.connection_settings import (
    ConnectionSettings,
    connection_settings_from_url,
)
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.fetch_schema_graph import count_edges, fetch_schema_graph
from brutal_sql.graph import EdgeType, Graph

pytestmark = pytest.mark.postgres

WRONG_USER = "wronguserwronguser"
WRONG_PASSWORD = "wrongpasswordwrongpassword"
EXPECTED_FORWARD_EDGES = {
    ("orders", "customer_id", "customer", "id"),
    ("order_items", "order_id", "orders", "id"),
    ("order_items", "product_id", "products", "id"),
}


def edges_of_type(graph: Graph, edge_type: EdgeType) -> set[tuple[str, ...]]:
    return {
        (node.name, edge.source_field, edge.target_table, edge.target_table_field)
        for node in graph.nodes
        for edge in node.edges
        if edge.edge_type == edge_type
    }


def assert_graph_matches_shop_schema(graph: Graph) -> None:
    assert graph.schema_name == "ant8_shop"
    names = sorted(node.name for node in graph.nodes)
    assert names == ["customer", "order_items", "orders", "products"]
    assert edges_of_type(graph, EdgeType.FORWARD) == EXPECTED_FORWARD_EDGES
    assert edges_of_type(graph, EdgeType.BACKWARD) == {
        (target, target_field, source, source_field)
        for source, source_field, target, target_field in EXPECTED_FORWARD_EDGES
    }
    assert count_edges(graph) == 6
    readable = {
        attribute.name: attribute.readable_name
        for attribute in graph.get_node("order_items").attributes
    }
    assert readable == {
        "id": "id",
        "order_id": "order_id",
        "product_id": "product_id",
        "quantity": "number of units",
    }
    assert graph.get_node("customer").attributes[1].readable_name == "customer name"


def test_fetch_schema_graph_builds_shop_graph(shop_schema: ConnectionSettings) -> None:
    graph = fetch_schema_graph(shop_schema)
    assert_graph_matches_shop_schema(graph)
    assert_graph_matches_shop_schema(Graph.from_json(graph.to_json()))


def test_fetch_schema_graph_from_url_with_credentials(
    shop_schema: ConnectionSettings,
) -> None:
    url = shop_schema.to_sqlalchemy_url().render_as_string(hide_password=False)
    settings = connection_settings_from_url(url, "ant8_shop")
    assert_graph_matches_shop_schema(fetch_schema_graph(settings))


def assert_fails_without_leaking(
    settings: ConnectionSettings,
    secrets: list[str],
    caplog: pytest.LogCaptureFixture,
) -> ProcessingError:
    with caplog.at_level(logging.DEBUG), pytest.raises(ProcessingError) as caught:
        fetch_schema_graph(settings)
    texts = [str(caught.value), repr(caught.value), str(caught.value.__cause__)]
    texts.append(caplog.text)
    leaked = any(secret in text for secret in secrets for text in texts)
    assert not leaked, "error text or logs leak a database username or password"
    return caught.value


def test_wrong_credentials_fail_without_leaking(
    shop_schema: ConnectionSettings, caplog: pytest.LogCaptureFixture
) -> None:
    settings = dataclasses.replace(
        shop_schema, username=WRONG_USER, password=WRONG_PASSWORD
    )
    error = assert_fails_without_leaking(
        settings, [WRONG_USER, WRONG_PASSWORD, str(shop_schema.password)], caplog
    )
    assert "password authentication failed" in str(error)


@pytest.mark.parametrize(
    "changes",
    [
        {"port": 1},
        {"host": "ant8-no-such-host.invalid"},
        {"database": "ant8_no_such_database"},
    ],
)
def test_wrong_url_fails_without_leaking(
    shop_schema: ConnectionSettings,
    changes: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = dataclasses.replace(shop_schema, **changes)
    error = assert_fails_without_leaking(settings, [str(shop_schema.password)], caplog)
    assert settings.describe_database() in str(error)


def test_wrong_schema_name_fails_without_leaking(
    shop_schema: ConnectionSettings, caplog: pytest.LogCaptureFixture
) -> None:
    settings = dataclasses.replace(shop_schema, schema_name="ant8_no_such_schema")
    error = assert_fails_without_leaking(settings, [str(shop_schema.password)], caplog)
    assert "ant8_no_such_schema" in str(error) and "not found" in str(error)

"""Definition of done for ANT-11, against the Docker Compose Postgres.

orders has two foreign keys to address (billing NOT NULL, shipping nullable);
complaints.order_id is a nullable foreign key to orders.
Never skipped: start the database with `docker compose up -d`.
"""

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow.fetch_schema_graph import fetch_schema_graph
from brutal_sql.graph import Edge, EdgeType, Graph

pytestmark = pytest.mark.postgres


def edges_between(graph: Graph, table: str, target: str) -> list[Edge]:
    return [edge for edge in graph.get_node(table).edges if edge.target_table == target]


def test_two_keys_to_address_give_two_edges_each_way(
    billing_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(billing_schema)
    forward = edges_between(graph, "orders", "address")
    backward = edges_between(graph, "address", "orders")
    assert {edge.edge_type for edge in forward} == {EdgeType.FORWARD}
    assert {edge.edge_type for edge in backward} == {EdgeType.BACKWARD}
    assert {edge.edge_id for edge in forward} == {
        "orders_billing_fkey",
        "orders_shipping_fkey",
    }
    assert {edge.edge_id for edge in backward} == {
        "orders_billing_fkey",
        "orders_shipping_fkey",
    }
    assert len(forward) == len(backward) == 2


def test_nullability_follows_the_foreign_key_columns(
    billing_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(billing_schema)
    nullable = {
        (node.name, edge.edge_type, edge.edge_id): edge.nullable
        for node in graph.nodes
        for edge in node.edges
    }
    assert nullable[("orders", EdgeType.FORWARD, "orders_billing_fkey")] is False
    assert nullable[("orders", EdgeType.FORWARD, "orders_shipping_fkey")] is True
    assert nullable[("address", EdgeType.BACKWARD, "orders_billing_fkey")] is False
    assert nullable[("address", EdgeType.BACKWARD, "orders_shipping_fkey")] is True
    complaint = edges_between(graph, "complaints", "orders")
    assert [edge.nullable for edge in complaint] == [True]


def test_forward_and_backward_edges_share_edge_id(
    billing_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(billing_schema)
    forward = edges_between(graph, "complaints", "orders")
    backward = edges_between(graph, "orders", "complaints")
    assert len(forward) == len(backward) == 1
    assert forward[0].edge_id == backward[0].edge_id == "complaints_order_id_fkey"


def test_every_fetched_edge_is_labelled(billing_schema: ConnectionSettings) -> None:
    graph = fetch_schema_graph(billing_schema)
    edges = [edge for node in graph.nodes for edge in node.edges]
    assert len(edges) == 6
    assert all(edge.edge_id for edge in edges)

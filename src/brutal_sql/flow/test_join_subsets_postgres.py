"""Definition of done for ANT-16: connected table sets of joins_shop.

Never skipped: start the database with `docker compose up -d`.
"""

from collections import Counter

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow import fetch_schema_graph
from brutal_sql.graph import Graph, find_connected_table_sets

pytestmark = pytest.mark.postgres


def shop_without_employee(settings: ConnectionSettings) -> Graph:
    graph = fetch_schema_graph(settings)
    graph.remove_node("managers")
    graph.remove_node("employee")
    return graph


def test_counts_by_size_on_joins_shop(joins_shop_schema: ConnectionSettings) -> None:
    graph = shop_without_employee(joins_shop_schema)
    assert sorted(node.name for node in graph.nodes) == [
        "complaints",
        "customer",
        "order_items",
        "orders",
        "products",
    ]
    sets = find_connected_table_sets(graph, 5)
    counts = Counter(len(tables) for tables in sets)
    assert [counts[size] for size in range(1, 6)] == [5, 5, 4, 3, 1]


def test_max_tables_two_on_joins_shop(joins_shop_schema: ConnectionSettings) -> None:
    sets = find_connected_table_sets(shop_without_employee(joins_shop_schema), 2)
    assert {len(tables) for tables in sets} == {1, 2}
    assert len(sets) == 10


def test_two_runs_give_the_same_order(joins_shop_schema: ConnectionSettings) -> None:
    first = find_connected_table_sets(shop_without_employee(joins_shop_schema), 5)
    second = find_connected_table_sets(shop_without_employee(joins_shop_schema), 5)
    assert first == second

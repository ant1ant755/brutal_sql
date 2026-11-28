"""Definition of done for ANT-18: one-table trees and all inner trees of joins_shop.

Never skipped: start the database with `docker compose up -d`.
"""

from collections import Counter

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow import find_all_join_trees
from brutal_sql.flow.test_join_subsets_postgres import shop_without_employee
from brutal_sql.graph import GraphError

pytestmark = pytest.mark.postgres


def test_one_table_gives_five_edgeless_trees(
    joins_shop_schema: ConnectionSettings,
) -> None:
    trees = find_all_join_trees(shop_without_employee(joins_shop_schema), 1)
    assert sorted(tree.root for tree in trees) == [
        "complaints",
        "customer",
        "order_items",
        "orders",
        "products",
    ]
    assert all(tree.edges == () and tree.tables == (tree.root,) for tree in trees)


def test_up_to_five_tables_gives_24_inner_trees(
    joins_shop_schema: ConnectionSettings,
) -> None:
    trees = find_all_join_trees(shop_without_employee(joins_shop_schema), 5)
    assert len(trees) == 24
    counts = Counter(len(tree.tables) for tree in trees)
    assert [counts[size] for size in range(1, 6)] == [5, 5, 6, 5, 3]


def test_invalid_max_tables_raises(joins_shop_schema: ConnectionSettings) -> None:
    graph = shop_without_employee(joins_shop_schema)
    with pytest.raises(GraphError, match="max_tables"):
        find_all_join_trees(graph, 0)

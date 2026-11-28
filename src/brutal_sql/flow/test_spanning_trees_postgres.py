"""Definition of done for ANT-17: spanning trees of joins_shop.

Never skipped: start the database with `docker compose up -d`.
"""

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow.test_join_subsets_postgres import shop_without_employee
from brutal_sql.graph import (
    JoinTree,
    JoinType,
    find_connected_table_sets,
    find_spanning_trees,
)

pytestmark = pytest.mark.postgres


def trees_by_size(settings: ConnectionSettings) -> dict[int, list[JoinTree]]:
    graph = shop_without_employee(settings)
    found: dict[int, list[JoinTree]] = {}
    for tables in find_connected_table_sets(graph, 5):
        found.setdefault(len(tables), []).extend(find_spanning_trees(graph, tables))
    return found


def test_tree_counts_by_size_on_joins_shop(
    joins_shop_schema: ConnectionSettings,
) -> None:
    found = trees_by_size(joins_shop_schema)
    assert [len(found[size]) for size in (2, 3, 4, 5)] == [5, 6, 5, 3]


def test_every_tree_is_a_valid_inner_join_tree(
    joins_shop_schema: ConnectionSettings,
) -> None:
    graph = shop_without_employee(joins_shop_schema)
    for trees in trees_by_size(joins_shop_schema).values():
        for tree in trees:
            rebuilt = JoinTree(tree.root, tree.tables, tree.edges, graph=graph)
            assert rebuilt == tree
            assert all(edge.join_type is JoinType.INNER for edge in tree.edges)

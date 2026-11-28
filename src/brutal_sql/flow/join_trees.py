"""Every inner join tree of a schema graph, from one table up to max_tables."""

from brutal_sql.graph import (
    Graph,
    JoinTree,
    find_connected_table_sets,
    find_spanning_trees,
)


def find_all_join_trees(graph: Graph, max_tables: int) -> list[JoinTree]:
    """Return every all-INNER join tree of 1 to max_tables tables.

    A one-table set gives one tree with no edges. Trees come in the order of
    their table sets (by size, then names), then in spanning-tree order.
    Raises GraphError for a max_tables that is not a positive integer.
    """
    trees: list[JoinTree] = []
    for tables in find_connected_table_sets(graph, max_tables):
        trees.extend(find_spanning_trees(graph, tables))
    return trees

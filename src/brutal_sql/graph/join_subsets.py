"""Find every set of tables that foreign keys connect, up to a size limit.

Each connected set is the starting point for its join trees. A set is
connected when every table can reach every other table through edges whose
two ends are both inside the set.
"""

from brutal_sql.graph.errors import GraphError
from brutal_sql.graph.schema_graph import Graph


def require_max_tables(max_tables: int) -> None:
    """Raise GraphError unless max_tables is a positive integer."""
    if isinstance(max_tables, bool) or not isinstance(max_tables, int):
        raise GraphError(f"max_tables must be an integer, got {max_tables!r}")
    if max_tables < 1:
        raise GraphError(f"max_tables must be at least 1, got {max_tables}")


def find_connected_table_sets(graph: Graph, max_tables: int) -> list[tuple[str, ...]]:
    """Return every connected set of 1 to max_tables tables.

    Each set is a tuple of sorted table names. Sets are ordered by size, then
    by their names, so two runs on the same graph give the same list.
    Raises GraphError for a max_tables that is not a positive integer.
    """
    if not isinstance(graph, Graph):
        raise GraphError(f"not a Graph: {graph!r}")
    require_max_tables(max_tables)
    neighbours = _neighbours_by_table(graph)
    current = {frozenset([table]) for table in neighbours}
    found = set(current)
    for _ in range(max_tables - 1):
        current = {
            table_set | {neighbour}
            for table_set in current
            for table in table_set
            for neighbour in neighbours[table] - table_set
        }
        found |= current
    named = [tuple(sorted(table_set)) for table_set in found]
    return sorted(named, key=lambda tables: (len(tables), tables))


def _neighbours_by_table(graph: Graph) -> dict[str, set[str]]:
    """Return each table's directly joined tables, in either key direction."""
    return {
        node.name: {edge.target_table for edge in node.edges} for node in graph.nodes
    }

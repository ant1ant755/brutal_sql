"""Every spanning tree of a table set: each one is a distinct inner join.

A spanning tree joins every table of the set with exactly (tables - 1) foreign
keys and no loop. Two foreign keys between the same two tables are different
edges, so they give different trees. The root is the first table by name.
"""

from collections import deque
from collections.abc import Sequence
from itertools import combinations
from typing import NamedTuple

from brutal_sql.graph.entity import EdgeType
from brutal_sql.graph.join_tree import JoinTree, JoinTreeError, JoinType, TreeEdge
from brutal_sql.graph.schema_graph import Graph


class ForeignKeyLink(NamedTuple):
    """One foreign key between two tables of a set: source -> target."""

    edge_id: str
    source: str
    target: str


def foreign_keys_within(graph: Graph, tables: Sequence[str]) -> list[ForeignKeyLink]:
    """Return each foreign key whose two tables are in the set, sorted.

    Raises JoinTreeError if such a foreign key has no edge_id.
    """
    inside = set(tables)
    links = []
    for table in tables:
        for edge in graph.get_node(table).edges:
            if edge.edge_type != EdgeType.FORWARD or edge.target_table not in inside:
                continue
            if edge.edge_id is None:
                raise JoinTreeError(
                    f"foreign key {table} -> {edge.target_table} has no edge_id"
                )
            links.append(ForeignKeyLink(edge.edge_id, table, edge.target_table))
    return sorted(links)


def find_spanning_trees(graph: Graph, tables: Sequence[str]) -> list[JoinTree]:
    """Return every spanning tree of the tables as an all-INNER JoinTree.

    Raises JoinTreeError for an empty set, a repeated table or a set the
    foreign keys do not connect, and NodeNotFoundError for an unknown table.
    """
    names = _require_table_set(tables)
    links = foreign_keys_within(graph, names)
    trees = [
        _orient(graph, names, chosen)
        for chosen in combinations(links, len(names) - 1)
        if _joins_without_loop(names, chosen)
    ]
    if not trees:
        raise JoinTreeError(f"tables {list(names)!r} are not connected")
    return trees


def _require_table_set(tables: Sequence[str]) -> tuple[str, ...]:
    """Return the tables sorted by name; raise if empty or repeated."""
    if isinstance(tables, str) or not tables:
        raise JoinTreeError(f"a table set needs at least one table, got {tables!r}")
    if len(set(tables)) != len(tables):
        raise JoinTreeError(f"table set lists a table twice: {tables!r}")
    return tuple(sorted(tables))


def _joins_without_loop(
    tables: Sequence[str], chosen: Sequence[ForeignKeyLink]
) -> bool:
    """True when the chosen keys join every table and never close a loop."""
    group = {table: table for table in tables}

    def find(table: str) -> str:
        while group[table] != table:
            table = group[table]
        return table

    for link in chosen:
        source, target = find(link.source), find(link.target)
        if source == target:
            return False
        group[source] = target
    return len({find(table) for table in tables}) == 1


def _orient(
    graph: Graph, tables: Sequence[str], chosen: Sequence[ForeignKeyLink]
) -> JoinTree:
    """Build the JoinTree rooted at the first table, edges pointing away from it."""
    root = tables[0]
    edges = []
    reached = {root}
    queue = deque([root])
    while queue:
        parent = queue.popleft()
        for link in chosen:
            if parent not in (link.source, link.target):
                continue
            child = link.target if link.source == parent else link.source
            if child not in reached:
                reached.add(child)
                queue.append(child)
                edges.append(TreeEdge(link.edge_id, parent, child, JoinType.INNER))
    return JoinTree(root, tables, tuple(edges), graph=graph)

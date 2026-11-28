"""A join tree: tables linked by foreign key edges, each edge with a join type.

A join tree is the unit of SQL generation. Unlike a chain (A -> B -> C), a tree
can branch: orders -> customer and orders -> order_items at once. Edges point
away from the root, from a parent table to a child table. Each edge names the
foreign key it follows by edge_id; either direction of that key may be used.
"""

from collections import deque
from dataclasses import InitVar, dataclass
from enum import StrEnum

from brutal_sql.graph.entity import require_text
from brutal_sql.graph.errors import GraphError
from brutal_sql.graph.schema_graph import Graph


class JoinType(StrEnum):
    """How a child table joins its parent."""

    INNER = "inner"
    LEFT = "left"
    ANTI = "anti"
    SEMI = "semi"


class JoinTreeError(GraphError):
    """Raised when a join tree or one of its edges is not valid."""


@dataclass(frozen=True)
class TreeEdge:
    """One join in a tree: parent table -> child table along foreign key edge_id.

    wrapped is True when the child's whole branch sits inside a bracket,
    EXISTS or NOT EXISTS.
    """

    edge_id: str
    parent_table: str
    child_table: str
    join_type: JoinType = JoinType.INNER
    wrapped: bool = False

    def __post_init__(self) -> None:
        require_text(self.edge_id, "edge_id")
        require_text(self.parent_table, "parent_table")
        require_text(self.child_table, "child_table")
        if self.parent_table == self.child_table:
            raise JoinTreeError(
                f"edge {self.edge_id!r} joins {self.parent_table!r} to itself"
            )
        if not isinstance(self.join_type, JoinType):
            raise JoinTreeError(f"join_type must be a JoinType: {self.join_type!r}")
        if not isinstance(self.wrapped, bool):
            raise JoinTreeError(f"wrapped must be a bool, got {self.wrapped!r}")


@dataclass(frozen=True)
class JoinTree:
    """A root table, the tables of the tree and the edges that link them.

    The graph is only used to check the tree when it is built; it is not kept.
    Raises JoinTreeError if the tree is not a valid tree of that graph.
    """

    root: str
    tables: tuple[str, ...]
    edges: tuple[TreeEdge, ...]
    graph: InitVar[Graph]

    def __post_init__(self, graph: Graph) -> None:
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "edges", tuple(self.edges))
        self._check_tables(graph)
        self._check_edge_count()
        self._check_parents()
        self._check_connected()
        for edge in self.edges:
            _require_graph_edge(graph, edge)

    def _check_tables(self, graph: Graph) -> None:
        """Require a non-empty set of unique graph tables that holds the root."""
        if not self.tables:
            raise JoinTreeError("a join tree needs at least one table")
        if len(set(self.tables)) != len(self.tables):
            raise JoinTreeError(f"join tree lists a table twice: {self.tables!r}")
        if self.root not in self.tables:
            raise JoinTreeError(f"root {self.root!r} is not a table of the tree")
        known = {node.name for node in graph.nodes}
        for table in self.tables:
            if table not in known:
                raise JoinTreeError(f"table {table!r} is not in the graph")

    def _check_edge_count(self) -> None:
        """A tree of n tables has n - 1 edges: more means a loop."""
        for edge in self.edges:
            if not isinstance(edge, TreeEdge):
                raise JoinTreeError(f"not a TreeEdge: {edge!r}")
        expected = len(self.tables) - 1
        if len(self.edges) > expected:
            raise JoinTreeError(
                f"join tree has a loop: {len(self.edges)} edges for "
                f"{len(self.tables)} tables (a tree has {expected})"
            )

    def _check_parents(self) -> None:
        """Every edge stays inside the tree and each table has at most one parent."""
        children: set[str] = set()
        for edge in self.edges:
            for table in (edge.parent_table, edge.child_table):
                if table not in self.tables:
                    raise JoinTreeError(
                        f"edge {edge.edge_id!r} uses {table!r}, not a table of the tree"
                    )
            if edge.child_table == self.root:
                raise JoinTreeError(f"root {self.root!r} cannot be a child")
            if edge.child_table in children:
                raise JoinTreeError(
                    f"join tree has a loop: {edge.child_table!r} has two parents"
                )
            children.add(edge.child_table)

    def _check_connected(self) -> None:
        """Every table is reachable from the root along the edges."""
        reached = {self.root}
        queue = deque([self.root])
        while queue:
            parent = queue.popleft()
            for edge in self.edges:
                if edge.parent_table == parent and edge.child_table not in reached:
                    reached.add(edge.child_table)
                    queue.append(edge.child_table)
        missing = [table for table in self.tables if table not in reached]
        if missing:
            raise JoinTreeError(
                f"join tree is disconnected: {missing!r} not reached from "
                f"root {self.root!r}"
            )


def _require_graph_edge(graph: Graph, tree_edge: TreeEdge) -> None:
    """Raise unless the graph has an edge edge_id going from parent to child."""
    if not _edge_id_known(graph, tree_edge.edge_id):
        raise JoinTreeError(f"unknown edge_id {tree_edge.edge_id!r}")
    parent = graph.get_node(tree_edge.parent_table)
    if not any(
        edge.edge_id == tree_edge.edge_id and edge.target_table == tree_edge.child_table
        for edge in parent.edges
    ):
        raise JoinTreeError(
            f"edge_id {tree_edge.edge_id!r} does not join "
            f"{tree_edge.parent_table!r} to {tree_edge.child_table!r}"
        )


def _edge_id_known(graph: Graph, edge_id: str) -> bool:
    """True when some edge of the graph carries this edge_id."""
    return any(edge.edge_id == edge_id for node in graph.nodes for edge in node.edges)

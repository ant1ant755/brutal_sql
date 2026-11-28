"""Graph of entities in one database schema, linked by foreign key edges."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from brutal_sql.graph.entity import Edge, EdgeType, EntityNode, require_text
from brutal_sql.graph.errors import DuplicateNodeError, GraphError, NodeNotFoundError
from brutal_sql.graph.foreign_key_edges import (
    build_foreign_key_edges,
    pair_foreign_key_columns,
    require_attribute,
    require_new_edge,
)
from brutal_sql.graph.join_step import JoinStep
from brutal_sql.graph.mirror import require_mirror_columns

__all__ = ["DEFAULT_MAX_JOINS", "Graph", "JoinStep", "count_backward_steps"]

DEFAULT_MAX_JOINS = 4


@dataclass(frozen=True)
class _PathSearch:
    """Settings shared by every step of one join path search."""

    start_table: str
    max_joins: int
    forward_only: bool


def count_backward_steps(path: list[JoinStep]) -> int:
    """Return how many steps in a join path follow backward edges."""
    return sum(1 for step in path if step.edge.edge_type == EdgeType.BACKWARD)


def _require_max_joins(max_joins: int) -> None:
    """Raise GraphError unless max_joins is a positive integer."""
    if isinstance(max_joins, bool) or not isinstance(max_joins, int):
        raise GraphError(f"max_joins must be an integer, got {max_joins!r}")
    if max_joins < 1:
        raise GraphError(f"max_joins must be at least 1, got {max_joins}")


class Graph:
    """Entities of one database schema and the foreign key edges between them."""

    def __init__(self, schema_name: str, nodes: list[EntityNode]) -> None:
        require_text(schema_name, "schema_name")
        if not nodes:
            raise GraphError(f"graph {schema_name!r} needs at least one node")
        self.schema_name = schema_name
        self._nodes: dict[str, EntityNode] = {}
        for node in nodes:
            self._require_new_node(node)
            self._nodes[node.name] = node
        for node in nodes:
            self._check_edge_targets(node)
            self._check_mirror_source(node)

    @property
    def nodes(self) -> list[EntityNode]:
        """All nodes in the order they were added."""
        return list(self._nodes.values())

    def to_json(self) -> str:
        """Return the graph as JSON text; Graph.from_json reverses it."""
        from brutal_sql.graph.serialization import graph_to_json

        return graph_to_json(self)

    @classmethod
    def from_json(cls, text: str) -> "Graph":
        """Rebuild a graph from to_json output; raise GraphError if invalid."""
        from brutal_sql.graph.serialization import graph_from_json

        return graph_from_json(text)

    def _require_new_node(self, node: EntityNode) -> None:
        """Reject non-nodes and names already in the graph."""
        if not isinstance(node, EntityNode):
            raise GraphError(f"not an EntityNode: {node!r}")
        if node.name in self._nodes:
            raise DuplicateNodeError(f"graph already has a node {node.name!r}")

    def _check_edge_targets(self, node: EntityNode) -> None:
        """Require every edge of node to point at an existing table and column."""
        for edge in node.edges:
            if edge.target_table == node.name:
                target = node
            else:
                target = self.get_node(edge.target_table)
            for target_field in edge.target_fields:
                require_attribute(target, target_field)

    def _check_mirror_source(self, node: EntityNode) -> None:
        """Require a mirror's physical table to be in the graph with its columns."""
        if node.mirror_of is None:
            return
        physical = self.get_node(node.mirror_of.physical_table)
        names = [attribute.name for attribute in physical.attributes]
        require_mirror_columns(node.mirror_of, names)

    def add_node(self, node: EntityNode) -> None:
        """Add a node whose edges point only at nodes already in the graph."""
        self._require_new_node(node)
        self._check_edge_targets(node)
        self._check_mirror_source(node)
        self._nodes[node.name] = node

    def get_node(self, table_name: str) -> EntityNode:
        """Return the node for table_name; raise NodeNotFoundError if absent."""
        if table_name not in self._nodes:
            raise NodeNotFoundError(f"graph has no node {table_name!r}")
        return self._nodes[table_name]

    def remove_node(self, table_name: str) -> EntityNode:
        """Remove a node and every edge pointing at it; the last node stays."""
        node = self.get_node(table_name)
        if len(self._nodes) == 1:
            raise GraphError(f"cannot remove {table_name!r}, the graph's last node")
        del self._nodes[table_name]
        for other in self._nodes.values():
            other.remove_edges_to(table_name)
        return node

    def add_foreign_key(
        self,
        source_table: str,
        source_field: str,
        target_table: str,
        target_field: str,
        forward_verb: str,
        backward_verb: str,
        *,
        edge_id: str | None = None,
        nullable: bool = False,
    ) -> tuple[Edge, Edge]:
        """Add a forward edge source -> target and a backward edge target -> source.

        Example: orders.customer_id -> customers.id with verbs 'placed by' and
        'places' adds orders -placed by-> customers and customers -places-> orders.
        Both edges get edge_id (the foreign key's name) and nullable.
        """
        return self.add_composite_foreign_key(
            source_table,
            [source_field],
            target_table,
            [target_field],
            forward_verb,
            backward_verb,
            edge_id=edge_id,
            nullable=nullable,
        )

    def add_composite_foreign_key(
        self,
        source_table: str,
        source_fields: Sequence[str],
        target_table: str,
        target_fields: Sequence[str],
        forward_verb: str,
        backward_verb: str,
        *,
        edge_id: str | None = None,
        nullable: bool = False,
    ) -> tuple[Edge, Edge]:
        """Add both edges of a foreign key on one or more columns, paired in order.

        Example: shipments(order_id, line_no) -> order_lines(order_id, line_no).
        Both edges get edge_id (the foreign key's name) and nullable.
        Raises GraphError if the column lists are empty or differ in length,
        and AttributeNotFoundError if a column is missing.
        """
        pairs = pair_foreign_key_columns(source_fields, target_fields)
        source_node = self.get_node(source_table)
        target_node = self.get_node(target_table)
        for source_field, target_field in pairs:
            require_attribute(source_node, source_field)
            require_attribute(target_node, target_field)
        forward, backward = build_foreign_key_edges(
            source_table,
            pairs,
            target_table,
            (forward_verb, backward_verb),
            edge_id=edge_id,
            nullable=nullable,
        )
        require_new_edge(source_node, forward)
        require_new_edge(target_node, backward)
        source_node.add_edge(forward)
        target_node.add_edge(backward)
        return forward, backward

    def remove_foreign_key(
        self, source_table: str, source_field: str, target_table: str, target_field: str
    ) -> tuple[Edge, Edge]:
        """Remove both edges of a foreign key; raise if either is missing."""
        source_node = self.get_node(source_table)
        target_node = self.get_node(target_table)
        forward = source_node.find_edge(
            EdgeType.FORWARD, source_field, target_table, target_field
        )
        backward = target_node.find_edge(
            EdgeType.BACKWARD, target_field, source_table, source_field
        )
        source_node.remove_edge(forward)
        target_node.remove_edge(backward)
        return forward, backward

    def neighbours(self, table_name: str, forward_only: bool = False) -> list[JoinStep]:
        """Return the direct joins out of a table, forward edges first."""
        node = self.get_node(table_name)
        forward = [edge for edge in node.edges if edge.edge_type == EdgeType.FORWARD]
        backward = (
            []
            if forward_only
            else [edge for edge in node.edges if edge.edge_type == EdgeType.BACKWARD]
        )
        return [JoinStep(table_name, edge) for edge in forward + backward]

    def join_options(self, table_a: str, table_b: str) -> list[JoinStep]:
        """Return every direct join from table_a to table_b (one per edge)."""
        self.get_node(table_b)
        steps = self.neighbours(table_a)
        return [step for step in steps if step.to_table == table_b]

    def walk_from(self, start_table: str, forward_only: bool = False) -> list[str]:
        """Return the tables reachable from start_table in breadth-first order."""
        order = [start_table]
        seen = {start_table}
        queue = deque([start_table])
        while queue:
            for step in self.neighbours(queue.popleft(), forward_only):
                if step.to_table not in seen:
                    seen.add(step.to_table)
                    order.append(step.to_table)
                    queue.append(step.to_table)
        return order

    def find_all_join_paths_from(
        self,
        start_table: str,
        max_joins: int = DEFAULT_MAX_JOINS,
        forward_only: bool = False,
    ) -> list[list[JoinStep]]:
        """Return every join path from start_table that never revisits a table.

        Paths are sorted by number of joins, then by number of backward steps.
        """
        self.get_node(start_table)
        _require_max_joins(max_joins)
        search = _PathSearch(start_table, max_joins, forward_only)
        found: list[list[JoinStep]] = []
        self._collect_paths(search, [], frozenset({start_table}), found)
        return sorted(found, key=lambda path: (len(path), count_backward_steps(path)))

    def _collect_paths(
        self,
        search: _PathSearch,
        path: list[JoinStep],
        visited: frozenset[str],
        found: list[list[JoinStep]],
    ) -> None:
        """Depth-first: extend path by each unvisited neighbour, recording each."""
        if len(path) == search.max_joins:
            return
        current = path[-1].to_table if path else search.start_table
        for step in self.neighbours(current, search.forward_only):
            if step.to_table in visited:
                continue
            extended = [*path, step]
            found.append(extended)
            self._collect_paths(search, extended, visited | {step.to_table}, found)

    def find_all_join_paths(
        self,
        start_table: str,
        end_table: str,
        max_joins: int = DEFAULT_MAX_JOINS,
        forward_only: bool = False,
    ) -> list[list[JoinStep]]:
        """Return every join path from start_table to end_table, shortest first."""
        self.get_node(end_table)
        if start_table == end_table:
            raise GraphError("start_table and end_table must be different tables")
        paths = self.find_all_join_paths_from(start_table, max_joins, forward_only)
        return [path for path in paths if path[-1].to_table == end_table]

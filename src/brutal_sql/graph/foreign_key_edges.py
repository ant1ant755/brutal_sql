"""Build the forward and backward edges of a foreign key on one or more columns."""

from collections.abc import Sequence

from brutal_sql.graph.entity import Edge, EdgeType, EntityNode
from brutal_sql.graph.errors import (
    AttributeNotFoundError,
    DuplicateEdgeError,
    GraphError,
)


def pair_foreign_key_columns(
    source_fields: Sequence[str], target_fields: Sequence[str]
) -> list[tuple[str, str]]:
    """Zip source and target columns in key order.

    Raises GraphError if either side is not a list of columns, is empty, or the
    two sides have different numbers of columns.
    """
    for fields in (source_fields, target_fields):
        if isinstance(fields, str) or not isinstance(fields, Sequence):
            raise GraphError(f"foreign key columns must be a list, got {fields!r}")
    if not source_fields:
        raise GraphError("a foreign key needs at least one column")
    if len(source_fields) != len(target_fields):
        raise GraphError(
            f"foreign key column counts differ: {len(source_fields)} source "
            f"columns, {len(target_fields)} target columns"
        )
    return list(zip(source_fields, target_fields))


def edge_along(
    pairs: Sequence[tuple[str, str]],
    target_table: str,
    verb_label: str,
    edge_type: EdgeType,
    *,
    edge_id: str | None = None,
    nullable: bool = False,
) -> Edge:
    """Return an edge joining along pairs; the first pair fills the main fields."""
    if not pairs:
        raise GraphError("an edge needs at least one column pair")
    (source_field, target_field), *extra = pairs
    return Edge(
        source_field,
        target_table,
        target_field,
        verb_label,
        edge_type,
        tuple(extra),
        edge_id=edge_id,
        nullable=nullable,
    )


def build_foreign_key_edges(
    source_table: str,
    pairs: Sequence[tuple[str, str]],
    target_table: str,
    verbs: tuple[str, str],
    *,
    edge_id: str | None = None,
    nullable: bool = False,
) -> tuple[Edge, Edge]:
    """Return (forward, backward) edges for a foreign key source -> target.

    verbs is (forward verb, backward verb). The backward edge swaps each pair.
    Both edges get the same edge_id and nullable.
    """
    forward = edge_along(
        pairs,
        target_table,
        verbs[0],
        EdgeType.FORWARD,
        edge_id=edge_id,
        nullable=nullable,
    )
    reversed_pairs = [(target, source) for source, target in pairs]
    backward = edge_along(
        reversed_pairs,
        source_table,
        verbs[1],
        EdgeType.BACKWARD,
        edge_id=edge_id,
        nullable=nullable,
    )
    return forward, backward


def require_attribute(node: EntityNode, attribute_name: str) -> None:
    """Raise AttributeNotFoundError unless node has the attribute."""
    if not node.has_attribute(attribute_name):
        raise AttributeNotFoundError(
            f"entity {node.name!r} has no attribute {attribute_name!r}"
        )


def require_new_edge(node: EntityNode, edge: Edge) -> None:
    """Raise DuplicateEdgeError if node already has this edge."""
    if edge in node.edges:
        raise DuplicateEdgeError(f"entity {node.name!r} already has {edge!r}")

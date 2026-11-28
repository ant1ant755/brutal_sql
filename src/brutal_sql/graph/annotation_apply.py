"""Apply an ontology annotations file to a schema graph (format: see annotations)."""

import dataclasses
from typing import Any

from brutal_sql.graph.annotations import (
    EDGE_KEYS,
    TODO_MARKER,
    AnnotationError,
    forward_edges_by_id,
    require_annotations_shape,
)
from brutal_sql.graph.entity import Edge, EdgeType, EntityNode, TableType
from brutal_sql.graph.schema_graph import Graph
from brutal_sql.graph.serialization import TABLE_TYPES


def apply_annotations(graph: Graph, annotations: dict[str, Any]) -> Graph:
    """Return a new graph with the file's table types, verbs and role names.

    The whole file is checked before anything is applied, and the input graph is
    left unchanged. A TODO value, or a table or edge missing from the file, keeps
    what the graph has. Raises AnnotationError for an unknown table or edge_id, an
    invalid type, a malformed entry, or a file for another schema.
    """
    require_annotations_shape(annotations)
    if annotations["schema_name"] != graph.schema_name:
        raise AnnotationError(
            f"annotations are for schema {annotations['schema_name']!r}, "
            f"not {graph.schema_name!r}"
        )
    table_types = _parse_tables(graph, annotations["tables"])
    edges = annotations["edges"]
    _check_edges(forward_edges_by_id(graph), edges)
    nodes = [_annotate_node(node, table_types, edges) for node in graph.nodes]
    return Graph(graph.schema_name, nodes)


def _parse_tables(graph: Graph, tables: dict[str, Any]) -> dict[str, TableType | None]:
    """Return table name -> type (None for TODO); raise for unknown names or types."""
    known = {node.name for node in graph.nodes}
    table_types = {}
    for table_name, entry in tables.items():
        if table_name not in known:
            raise AnnotationError(f"unknown table {table_name!r} in annotations")
        table_types[table_name] = _parse_table_type(table_name, entry)
    return table_types


def _parse_table_type(table_name: str, entry: object) -> TableType | None:
    """Return the table's type from its entry, or None when it is still TODO."""
    if not isinstance(entry, dict) or "type" not in entry:
        raise AnnotationError(f"table {table_name!r} entry needs a 'type' key")
    value = entry["type"]
    if value == TODO_MARKER:
        return None
    table_type = TABLE_TYPES.get(value) if isinstance(value, str) else None
    if table_type is None:
        raise AnnotationError(
            f"table {table_name!r} has invalid type {value!r}; "
            f"expected one of {sorted(TABLE_TYPES)} or {TODO_MARKER!r}"
        )
    return table_type


def _check_edges(
    forward_edges: dict[str, tuple[str, Edge]], edges: dict[str, Any]
) -> None:
    """Raise AnnotationError for an unknown edge_id or a malformed edge entry."""
    for edge_id, entry in edges.items():
        if edge_id not in forward_edges:
            raise AnnotationError(f"unknown edge_id {edge_id!r} in annotations")
        if not isinstance(entry, dict):
            raise AnnotationError(f"edge {edge_id!r} entry must be a dict")
        missing = [key for key in EDGE_KEYS if key not in entry]
        if missing:
            raise AnnotationError(f"edge {edge_id!r} entry is missing {missing!r}")
        source_table, edge = forward_edges[edge_id]
        if (entry["from_table"], entry["to_table"]) != (
            source_table,
            edge.target_table,
        ):
            raise AnnotationError(
                f"edge {edge_id!r} joins {source_table!r} -> {edge.target_table!r}, "
                f"not {entry['from_table']!r} -> {entry['to_table']!r}"
            )
        _check_edge_values(edge_id, entry)


def _check_edge_values(edge_id: str, entry: dict[str, Any]) -> None:
    """Require non-blank verbs, and a role name that is non-blank text or null."""
    for key in ("verb_forward", "verb_backward"):
        if not _is_text(entry[key]):
            raise AnnotationError(
                f"edge {edge_id!r} {key} must be non-blank text, got {entry[key]!r}"
            )
    if entry["role_name"] is not None and not _is_text(entry["role_name"]):
        raise AnnotationError(
            f"edge {edge_id!r} role_name must be non-blank text or null, "
            f"got {entry['role_name']!r}"
        )


def _is_text(value: object) -> bool:
    """True for a string with non-blank text."""
    return isinstance(value, str) and bool(value.strip())


def _annotate_node(
    node: EntityNode,
    table_types: dict[str, TableType | None],
    edges: dict[str, Any],
) -> EntityNode:
    """Return a copy of node with its type and the verbs of its edges filled in."""
    table_type = table_types.get(node.name) or node.table_type
    annotated_edges = [
        _annotate_edge(edge, edges.get(edge.edge_id)) for edge in node.edges
    ]
    return dataclasses.replace(node, edges=annotated_edges, table_type=table_type)


def _annotate_edge(edge: Edge, entry: dict[str, Any] | None) -> Edge:
    """Return edge with its verb and role name from entry; TODO keeps the old value."""
    if entry is None:
        return edge
    verb_key = "verb_forward" if edge.edge_type == EdgeType.FORWARD else "verb_backward"
    return dataclasses.replace(
        edge,
        verb_label=_value_or_current(entry[verb_key], edge.verb_label),
        role_name=_value_or_current(entry["role_name"], edge.role_name),
    )


def _value_or_current(value: Any, current: Any) -> Any:
    """Return value, or current when value is still the TODO marker."""
    return current if value == TODO_MARKER else value

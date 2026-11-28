"""Convert a schema graph to and from JSON-ready dictionaries and JSON text."""

import json
from typing import Any

from brutal_sql.graph.entity import Edge, EdgeType, EntityAttribute, EntityNode
from brutal_sql.graph.errors import GraphError
from brutal_sql.graph.mirror import MirrorSource, RowFilter
from brutal_sql.graph.schema_graph import Graph

FORMAT_VERSION = 1
EDGE_TYPES = {edge_type.value: edge_type for edge_type in EdgeType}
ROW_FILTERS = {row_filter.value: row_filter for row_filter in RowFilter}


def graph_to_dict(graph: Graph) -> dict[str, Any]:
    """Return the graph as plain dicts and lists, ready for json.dumps."""
    return {
        "format_version": FORMAT_VERSION,
        "schema_name": graph.schema_name,
        "nodes": [_node_to_dict(node) for node in graph.nodes],
    }


def _node_to_dict(node: EntityNode) -> dict[str, Any]:
    """Return one node with its attributes and edges as plain dicts."""
    return {
        "name": node.name,
        "attributes": [
            {"name": attribute.name, "readable_name": attribute.readable_name}
            for attribute in node.attributes
        ],
        "edges": [_edge_to_dict(edge) for edge in node.edges],
        "mirror_of": _mirror_to_dict(node.mirror_of),
    }


def _mirror_to_dict(source: MirrorSource | None) -> dict[str, Any] | None:
    """Return a mirror's source as a plain dict, or None for an ordinary node."""
    if source is None:
        return None
    return {
        "physical_table": source.physical_table,
        "referencing_column": source.referencing_column,
        "referenced_column": source.referenced_column,
        "column_mapping": [list(pair) for pair in source.column_mapping],
        "row_filter": source.row_filter.value,
    }


def _edge_to_dict(edge: Edge) -> dict[str, Any]:
    """Return one edge as a plain dict; extra pairs of a composite key as lists."""
    return {
        "source_field": edge.source_field,
        "target_table": edge.target_table,
        "target_table_field": edge.target_table_field,
        "verb_label": edge.verb_label,
        "edge_type": edge.edge_type.value,
        "extra_column_pairs": [list(pair) for pair in edge.extra_column_pairs],
    }


def graph_from_dict(data: dict[str, Any]) -> Graph:
    """Rebuild a graph from graph_to_dict output; raise GraphError if malformed."""
    if not isinstance(data, dict):
        raise GraphError(f"graph data must be a dict, got {type(data).__name__}")
    if data.get("format_version") != FORMAT_VERSION:
        raise GraphError(f"unsupported graph format {data.get('format_version')!r}")
    try:
        nodes = [_node_from_dict(node) for node in data["nodes"]]
        return Graph(data["schema_name"], nodes)
    except (KeyError, TypeError, AttributeError) as error:
        raise GraphError(f"malformed graph data: {error!r}") from error


def _node_from_dict(data: dict[str, Any]) -> EntityNode:
    """Rebuild one node, its attributes and its edges."""
    attributes = [
        EntityAttribute(attribute["name"], attribute["readable_name"])
        for attribute in data["attributes"]
    ]
    edges = [_edge_from_dict(edge) for edge in data["edges"]]
    mirror_of = _mirror_from_dict(data.get("mirror_of"))
    return EntityNode(data["name"], attributes, edges, mirror_of)


def _mirror_from_dict(data: dict[str, Any] | None) -> MirrorSource | None:
    """Rebuild a mirror's source; None (or a missing key) means an ordinary node."""
    if data is None:
        return None
    row_filter = ROW_FILTERS.get(data["row_filter"])
    if row_filter is None:
        raise GraphError(f"unknown row_filter {data['row_filter']!r}")
    return MirrorSource(
        data["physical_table"],
        data["referencing_column"],
        data["referenced_column"],
        tuple(_pair_from_list(pair) for pair in data["column_mapping"]),
        row_filter,
    )


def _pair_from_list(
    pair: object, field_name: str = "column_mapping"
) -> tuple[object, ...]:
    """Return a two-column list as a tuple; raise GraphError otherwise."""
    if not isinstance(pair, list):
        raise GraphError(f"{field_name} entry must be a list, got {pair!r}")
    return tuple(pair)


def _extra_pairs_from_list(pairs: object) -> tuple[tuple[object, ...], ...]:
    """Rebuild an edge's extra column pairs; a missing key (None) means none."""
    if pairs is None:
        return ()
    if not isinstance(pairs, list):
        raise GraphError(f"extra_column_pairs must be a list, got {pairs!r}")
    return tuple(_pair_from_list(pair, "extra_column_pairs") for pair in pairs)


def _edge_from_dict(data: dict[str, Any]) -> Edge:
    """Rebuild one edge; raise GraphError for an unknown edge type."""
    edge_type = EDGE_TYPES.get(data["edge_type"])
    if edge_type is None:
        raise GraphError(f"unknown edge_type {data['edge_type']!r}")
    return Edge(
        data["source_field"],
        data["target_table"],
        data["target_table_field"],
        data["verb_label"],
        edge_type,
        _extra_pairs_from_list(data.get("extra_column_pairs")),
    )


def graph_to_json(graph: Graph) -> str:
    """Return the graph as indented JSON text."""
    return json.dumps(graph_to_dict(graph), indent=2)


def graph_from_json(text: str) -> Graph:
    """Rebuild a graph from graph_to_json output; raise GraphError if invalid."""
    if not isinstance(text, str):
        raise GraphError(f"graph JSON must be a string, got {type(text).__name__}")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise GraphError(f"invalid graph JSON: {error}") from error
    return graph_from_dict(data)

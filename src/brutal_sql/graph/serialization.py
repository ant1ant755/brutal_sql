"""Convert a schema graph to and from JSON-ready dictionaries and JSON text."""

import json
from typing import Any

from brutal_sql.graph.entity import Edge, EdgeType, EntityAttribute, EntityNode
from brutal_sql.graph.errors import GraphError
from brutal_sql.graph.schema_graph import Graph

FORMAT_VERSION = 1
EDGE_TYPES = {edge_type.value: edge_type for edge_type in EdgeType}


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
    }


def _edge_to_dict(edge: Edge) -> dict[str, str]:
    """Return one edge as a plain dict."""
    return {
        "source_field": edge.source_field,
        "target_table": edge.target_table,
        "target_table_field": edge.target_table_field,
        "verb_label": edge.verb_label,
        "edge_type": edge.edge_type.value,
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
    return EntityNode(data["name"], attributes, edges)


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

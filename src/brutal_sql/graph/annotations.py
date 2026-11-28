"""Ontology annotations: table types, real verbs and role names for a schema graph.

The graph built from a database schema only has placeholder verbs ("references" /
"referenced by") and no table types. An annotations file, kept as JSON next to the
generated graph, fills them in:

* ``tables``: table name -> ``type``, either ``"entity"`` or ``"dimension"``. Only
  entity tables can be the root of a join tree.
* ``edges``: foreign key ``edge_id`` -> ``verb_forward`` (used on the edge from the
  referencing table), ``verb_backward`` (used on the edge back to it) and
  ``role_name`` (text, or ``null`` when the foreign key needs none). Role names tell
  apart two foreign keys between the same tables, e.g. "billing" and "shipping".
  ``from_table`` and ``to_table`` say which tables the foreign key joins; they help
  people read the file and must match the graph when the file is applied.

Example::

    {
      "format_version": 1,
      "schema_name": "ant8_shop",
      "tables": {
        "customer": {"type": "entity"},
        "orders": {"type": "entity"}
      },
      "edges": {
        "orders_customer_id_fkey": {
          "from_table": "orders",
          "to_table": "customer",
          "verb_forward": "placed by",
          "verb_backward": "places",
          "role_name": null
        }
      }
    }

``draft_annotations(graph)`` writes such a file for every table and every
``edge_id`` of a graph, with each value set to ``"TODO"``. ``apply_annotations``
(in ``annotation_apply``) copies the values onto a new graph. A value still set to
``"TODO"``, or a table or edge left out of the file, keeps what the graph has: no
table type, the placeholder verbs, no role name. The ontology validator reports
those gaps.
"""

import json
from typing import Any

from brutal_sql.graph.entity import Edge, EdgeType
from brutal_sql.graph.errors import GraphError
from brutal_sql.graph.schema_graph import Graph

ANNOTATIONS_FORMAT_VERSION = 1
TODO_MARKER = "TODO"
EDGE_KEYS = ("from_table", "to_table", "verb_forward", "verb_backward", "role_name")


class AnnotationError(GraphError):
    """Raised when an annotations file is malformed or does not match the graph."""


def forward_edges_by_id(graph: Graph) -> dict[str, tuple[str, Edge]]:
    """Return edge_id -> (referencing table, forward edge) for every foreign key.

    Raises AnnotationError if an edge has no edge_id, or two foreign keys share one.
    """
    found: dict[str, tuple[str, Edge]] = {}
    for node in graph.nodes:
        for edge in node.edges:
            if edge.edge_id is None:
                raise AnnotationError(
                    f"edge {node.name}.{edge.source_field} -> {edge.target_table} "
                    "has no edge_id, so it cannot be annotated"
                )
            if edge.edge_type != EdgeType.FORWARD:
                continue
            if edge.edge_id in found:
                raise AnnotationError(
                    f"edge_id {edge.edge_id!r} names more than one foreign key"
                )
            found[edge.edge_id] = (node.name, edge)
    return found


def draft_annotations(graph: Graph) -> dict[str, Any]:
    """Return an annotations dict for every table and edge_id, all values TODO.

    Raises AnnotationError if an edge has no edge_id, or two foreign keys share one.
    """
    edges = {
        edge_id: _draft_edge_entry(source_table, edge)
        for edge_id, (source_table, edge) in forward_edges_by_id(graph).items()
    }
    return {
        "format_version": ANNOTATIONS_FORMAT_VERSION,
        "schema_name": graph.schema_name,
        "tables": {node.name: {"type": TODO_MARKER} for node in graph.nodes},
        "edges": edges,
    }


def _draft_edge_entry(source_table: str, edge: Edge) -> dict[str, str]:
    """Return the draft entry of one foreign key: its tables, then TODO values."""
    return {
        "from_table": source_table,
        "to_table": edge.target_table,
        "verb_forward": TODO_MARKER,
        "verb_backward": TODO_MARKER,
        "role_name": TODO_MARKER,
    }


def annotations_to_json(annotations: dict[str, Any]) -> str:
    """Return an annotations dict as indented JSON text."""
    return json.dumps(annotations, indent=2)


def annotations_from_json(text: str) -> dict[str, Any]:
    """Parse annotations JSON text; raise AnnotationError if it is not valid."""
    if not isinstance(text, str):
        raise AnnotationError(
            f"annotations JSON must be a string, got {type(text).__name__}"
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise AnnotationError(f"invalid annotations JSON: {error}") from error
    require_annotations_shape(data)
    return data


def require_annotations_shape(data: object) -> None:
    """Raise AnnotationError unless data has the version, schema, tables and edges."""
    if not isinstance(data, dict):
        raise AnnotationError(f"annotations must be a dict, got {type(data).__name__}")
    if data.get("format_version") != ANNOTATIONS_FORMAT_VERSION:
        raise AnnotationError(
            f"unsupported annotations format {data.get('format_version')!r}"
        )
    if not isinstance(data.get("schema_name"), str):
        raise AnnotationError("annotations need a schema_name string")
    for section in ("tables", "edges"):
        if not isinstance(data.get(section), dict):
            raise AnnotationError(f"annotations need a {section!r} dict")

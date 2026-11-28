"""Flows that fetch a database schema and turn it into an entity graph."""

from brutal_sql.flow.annotated_graph import build_annotated_graph
from brutal_sql.flow.fetch_schema_graph import count_edges, fetch_schema_graph
from brutal_sql.flow.schema_to_graph import (
    BACKWARD_VERB,
    FORWARD_VERB,
    add_foreign_key_edges,
    build_entity_node,
    convert_tables_to_graph,
    readable_name_for,
)

__all__ = [
    "BACKWARD_VERB",
    "FORWARD_VERB",
    "add_foreign_key_edges",
    "build_annotated_graph",
    "build_entity_node",
    "convert_tables_to_graph",
    "count_edges",
    "fetch_schema_graph",
    "readable_name_for",
]

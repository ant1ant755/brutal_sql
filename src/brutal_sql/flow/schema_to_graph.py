"""Turn table metadata read from a database into an entity graph."""

import dataclasses
import logging

from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.foreign_key_identity import edge_id_for, is_foreign_key_nullable
from brutal_sql.flow.self_reference import add_mirror_tables, is_self_referencing
from brutal_sql.graph import EntityAttribute, EntityNode, Graph, GraphError

logger = logging.getLogger(__name__)

# Placeholder verbs until users name relationships themselves.
FORWARD_VERB = "references"
BACKWARD_VERB = "referenced by"


def readable_name_for(column: ColumnMetadata) -> str:
    """Return the column comment if it has text, otherwise the column name."""
    if column.comment and column.comment.strip():
        return column.comment.strip()
    return column.name


def build_entity_node(table: TableMetadata) -> EntityNode:
    """Return a node for the table, one attribute per column, with no edges yet."""
    attributes = [
        EntityAttribute(column.name, readable_name_for(column))
        for column in table.columns
    ]
    return EntityNode(table.name, attributes)


def _skip_reason(
    table: TableMetadata, foreign_key: ForeignKeyMetadata, schema_name: str
) -> str | None:
    """Return why a foreign key can't become an edge yet, or None if it can."""
    if foreign_key.referred_schema != schema_name:
        # TODO: support foreign keys to tables in another schema.
        return f"it points at schema {foreign_key.referred_schema!r}"
    if foreign_key.referred_table == table.name:
        # Self joins become mirror tables (see flow.self_reference), which
        # convert_tables_to_graph adds instead of a self-loop edge.
        return "it references its own table (self join)"
    return None


def _add_edges_for(
    graph: Graph, table: TableMetadata, foreign_key: ForeignKeyMetadata
) -> None:
    """Add both edges of one foreign key, labelled with its name and nullability."""
    graph.add_composite_foreign_key(
        table.name,
        foreign_key.column_names,
        foreign_key.referred_table,
        foreign_key.referred_column_names,
        FORWARD_VERB,
        BACKWARD_VERB,
        edge_id=edge_id_for(table, foreign_key),
        nullable=is_foreign_key_nullable(table, foreign_key),
    )


def add_foreign_key_edges(graph: Graph, table: TableMetadata) -> int:
    """Add forward and backward edges for each supported foreign key of table.

    A composite foreign key becomes one edge each way holding every column
    pair. Each edge carries the foreign key's name (edge_id) and whether its
    columns can be NULL. Unsupported or repeated foreign keys are skipped with
    a warning.
    Returns the number of foreign keys added.
    """
    added: set[tuple[tuple[str, ...], str, tuple[str, ...]]] = set()
    for foreign_key in table.foreign_keys:
        reason = _skip_reason(table, foreign_key, graph.schema_name)
        key = (
            foreign_key.column_names,
            foreign_key.referred_table,
            foreign_key.referred_column_names,
        )
        if reason is None and key in added:
            reason = "an identical foreign key was already added"
        if reason is not None:
            logger.warning("Skipping foreign key %r on %r: %s", key, table.name, reason)
            continue
        _add_edges_for(graph, table, foreign_key)
        added.add(key)
    return len(added)


def without_self_references(table: TableMetadata, schema_name: str) -> TableMetadata:
    """Return a copy of table without its self-referencing foreign keys.

    Those become mirror tables, so they must not be warned about as skipped.
    """
    kept = tuple(
        foreign_key
        for foreign_key in table.foreign_keys
        if not is_self_referencing(table, foreign_key, schema_name)
    )
    return dataclasses.replace(table, foreign_keys=kept)


def convert_tables_to_graph(schema_name: str, tables: list[TableMetadata]) -> Graph:
    """Build the entity graph of a schema from its tables' metadata.

    A self-referencing table also gets a graph-only mirror node; see
    flow.self_reference. Raises ProcessingError if the graph is invalid.
    """
    if not tables:
        raise ProcessingError(f"schema {schema_name!r} has no tables to convert")
    try:
        graph = Graph(schema_name, [build_entity_node(table) for table in tables])
        for table in tables:
            add_foreign_key_edges(graph, without_self_references(table, schema_name))
        for table in tables:
            add_mirror_tables(graph, table)
    except GraphError as error:
        raise ProcessingError(
            f"could not build the entity graph for schema {schema_name!r}: {error}"
        ) from error
    return graph

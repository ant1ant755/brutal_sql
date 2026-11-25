"""Turn table metadata read from a database into an entity graph."""

import logging

from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)
from brutal_sql.errors import ProcessingError
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
        # TODO: support self-referencing foreign keys (self joins), e.g.
        # employees.manager_id -> employees.id.
        return "it references its own table (self join)"
    if foreign_key.is_composite:
        # TODO: support composite foreign keys with a multi-column edge.
        return "it spans more than one column"
    return None


def add_foreign_key_edges(graph: Graph, table: TableMetadata) -> int:
    """Add forward and backward edges for each supported foreign key of table.

    Unsupported or repeated foreign keys are skipped with a warning.
    Returns the number of foreign keys added.
    """
    added: set[tuple[str, str, str]] = set()
    for foreign_key in table.foreign_keys:
        reason = _skip_reason(table, foreign_key, graph.schema_name)
        key = (
            foreign_key.column_names[0],
            foreign_key.referred_table,
            foreign_key.referred_column_names[0],
        )
        if reason is None and key in added:
            reason = "an identical foreign key was already added"
        if reason is not None:
            logger.warning("Skipping foreign key %r on %r: %s", key, table.name, reason)
            continue
        graph.add_foreign_key(table.name, *key, FORWARD_VERB, BACKWARD_VERB)
        added.add(key)
    return len(added)


def convert_tables_to_graph(schema_name: str, tables: list[TableMetadata]) -> Graph:
    """Build the entity graph of a schema from its tables' metadata."""
    if not tables:
        raise ProcessingError(f"schema {schema_name!r} has no tables to convert")
    try:
        graph = Graph(schema_name, [build_entity_node(table) for table in tables])
        for table in tables:
            add_foreign_key_edges(graph, table)
    except GraphError as error:
        raise ProcessingError(
            f"could not build the entity graph for schema {schema_name!r}: {error}"
        ) from error
    return graph

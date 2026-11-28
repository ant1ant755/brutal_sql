"""Model self-referencing foreign keys as graph-only mirror tables.

employee(id, manager_id, name) with manager_id -> employee.id gets a mirror
node managers(id, name): the referenced column is dropped and manager_id is
renamed to id. Edges employee.manager_id <-> managers.id replace the
self-loop. Nothing is created in the database.
"""

from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)
from brutal_sql.errors import ProcessingError
from brutal_sql.graph import (
    EntityAttribute,
    EntityNode,
    Graph,
    MirrorSource,
    RowFilter,
)

# Placeholder verbs until users name relationships themselves.
MIRROR_FORWARD_VERB = "references"
MIRROR_BACKWARD_VERB = "referenced by"


def is_self_referencing(
    table: TableMetadata, foreign_key: ForeignKeyMetadata, schema_name: str
) -> bool:
    """True for a single-column foreign key to its own table in the same schema."""
    return (
        foreign_key.referred_schema == schema_name
        and foreign_key.referred_table == table.name
        and not foreign_key.is_composite
    )


def mirror_table_name(column_name: str) -> str:
    """Return the mirror's name from the foreign key column: manager_id -> managers."""
    if not isinstance(column_name, str) or not column_name.strip():
        raise ProcessingError(f"column name must be non-blank, got {column_name!r}")
    base = column_name.strip()
    if base.lower().endswith("_id") and len(base) > 3:
        base = base[:-3]
    return base if base.endswith("s") else f"{base}s"


def _readable_name(column: ColumnMetadata) -> str:
    """Return the column comment if it has text, otherwise the column name."""
    comment = column.comment.strip() if column.comment else ""
    return comment or column.name


def _require_self_reference(
    table: TableMetadata, foreign_key: ForeignKeyMetadata
) -> None:
    """Raise ProcessingError unless foreign_key is a single-column self reference."""
    if foreign_key.referred_table != table.name or foreign_key.is_composite:
        raise ProcessingError(
            f"foreign key on {table.name!r} is not a single-column self reference"
        )


def mirror_column_names(
    table: TableMetadata, foreign_key: ForeignKeyMetadata
) -> list[str]:
    """Return the mirror's columns: referenced column dropped, key column renamed.

    Raises ProcessingError if the key is not a single-column self reference.
    """
    _require_self_reference(table, foreign_key)
    referencing = foreign_key.column_names[0]
    referenced = foreign_key.referred_column_names[0]
    return [
        referenced if column.name == referencing else column.name
        for column in table.columns
        if column.name != referenced
    ]


def build_mirror_node(
    table: TableMetadata, foreign_key: ForeignKeyMetadata
) -> EntityNode:
    """Return the mirror node of a self-referencing table for one foreign key.

    Each mirror column maps to the physical column of the same name on the
    referenced row, e.g. managers.id -> employee.id, managers.name -> employee.name.
    Raises ProcessingError if the key is not self-referencing.
    """
    columns = {column.name: column for column in table.columns}
    names = mirror_column_names(table, foreign_key)
    source = MirrorSource(
        table.name,
        foreign_key.column_names[0],
        foreign_key.referred_column_names[0],
        tuple((name, name) for name in names),
        RowFilter.ONLY_REFERENCED_ROWS,
    )
    attributes = [
        EntityAttribute(name, _readable_name(columns[name])) for name in names
    ]
    return EntityNode(
        mirror_table_name(source.referencing_column), attributes, mirror_of=source
    )


def _require_free_name(graph: Graph, mirror: EntityNode, table_name: str) -> None:
    """Raise ProcessingError if the mirror's name is already a node in the graph."""
    if mirror.name in {node.name for node in graph.nodes}:
        raise ProcessingError(
            f"cannot add mirror {mirror.name!r} of {table_name!r}: "
            "a table with that name already exists"
        )


def add_mirror_tables(graph: Graph, table: TableMetadata) -> int:
    """Add a mirror node and its two edges for each self-referencing foreign key.

    Raises ProcessingError if a mirror's name is already a node in the graph.
    Returns the number of mirrors added.
    """
    added = 0
    for foreign_key in table.foreign_keys:
        if not is_self_referencing(table, foreign_key, graph.schema_name):
            continue
        mirror = build_mirror_node(table, foreign_key)
        _require_free_name(graph, mirror, table.name)
        graph.add_node(mirror)
        graph.add_foreign_key(
            table.name,
            foreign_key.column_names[0],
            mirror.name,
            foreign_key.referred_column_names[0],
            MIRROR_FORWARD_VERB,
            MIRROR_BACKWARD_VERB,
        )
        added += 1
    return added

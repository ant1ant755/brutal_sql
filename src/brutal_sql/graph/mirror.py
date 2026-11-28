"""Mirror tables: graph-only copies of a self-referencing table.

A table whose foreign key points at itself, e.g. employee.manager_id ->
employee.id, gets a mirror node (managers) in the graph. The mirror exists
only in the graph; MirrorSource records how to rebuild it from the physical
table as a derived table when SQL is written.
"""

from dataclasses import dataclass
from enum import StrEnum

from brutal_sql.graph.errors import AttributeNotFoundError, GraphError


def _require_text(value: object, field_name: str) -> None:
    """Raise GraphError unless value is a string with non-blank text."""
    if not isinstance(value, str) or not value.strip():
        raise GraphError(f"{field_name} must be a non-blank string, got {value!r}")


class RowFilter(StrEnum):
    """Which rows of the physical table belong to the mirror."""

    ONLY_REFERENCED_ROWS = "only_referenced_rows"


@dataclass(frozen=True)
class MirrorSource:
    """How to rebuild a mirror table from the physical table it copies.

    column_mapping pairs each mirror column with the physical column it reads,
    e.g. (("id", "id"), ("name", "name")). With ONLY_REFERENCED_ROWS the mirror
    holds each physical row that some row's referencing_column points at, once.
    """

    physical_table: str
    referencing_column: str
    referenced_column: str
    column_mapping: tuple[tuple[str, str], ...]
    row_filter: RowFilter = RowFilter.ONLY_REFERENCED_ROWS

    def __post_init__(self) -> None:
        _require_text(self.physical_table, "physical_table")
        _require_text(self.referencing_column, "referencing_column")
        _require_text(self.referenced_column, "referenced_column")
        self._check_column_mapping()
        if not isinstance(self.row_filter, RowFilter):
            raise GraphError(f"row_filter must be a RowFilter, got {self.row_filter!r}")

    def _check_column_mapping(self) -> None:
        """Require a non-empty tuple of (mirror, physical) name pairs, unique."""
        if not isinstance(self.column_mapping, tuple) or not self.column_mapping:
            raise GraphError("column_mapping must be a non-empty tuple of pairs")
        for pair in self.column_mapping:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise GraphError(f"column_mapping entry is not a pair: {pair!r}")
            _require_text(pair[0], "mirror column")
            _require_text(pair[1], "physical column")
        mirror_columns = self.mirror_columns
        if len(mirror_columns) != len(set(mirror_columns)):
            raise GraphError("column_mapping has duplicate mirror columns")

    @property
    def mirror_columns(self) -> list[str]:
        """The mirror's column names, in mapping order."""
        return [mirror_column for mirror_column, _ in self.column_mapping]

    @property
    def physical_columns(self) -> list[str]:
        """The physical columns the mirror reads, in mapping order."""
        return [physical_column for _, physical_column in self.column_mapping]

    def to_derived_table_sql(self) -> str:
        """Return the SELECT that yields the mirror's rows from the physical table.

        Example: SELECT DISTINCT m.id, m.name FROM employee AS e
        JOIN employee AS m ON e.manager_id = m.id
        """
        selected = ", ".join(
            f"m.{physical}" if physical == mirror else f"m.{physical} AS {mirror}"
            for mirror, physical in self.column_mapping
        )
        return (
            f"SELECT DISTINCT {selected} "
            f"FROM {self.physical_table} AS e "
            f"JOIN {self.physical_table} AS m "
            f"ON e.{self.referencing_column} = m.{self.referenced_column}"
        )


def require_mirror_columns(source: MirrorSource, physical_columns: list[str]) -> None:
    """Raise AttributeNotFoundError unless the physical table has every column used."""
    needed = [
        *source.physical_columns,
        source.referencing_column,
        source.referenced_column,
    ]
    for column_name in needed:
        if column_name not in physical_columns:
            raise AttributeNotFoundError(
                f"physical table {source.physical_table!r} "
                f"has no column {column_name!r}"
            )

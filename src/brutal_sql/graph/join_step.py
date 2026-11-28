"""One join between two tables of the schema graph, and its SQL condition."""

from dataclasses import dataclass

from brutal_sql.graph.entity import Edge, require_text
from brutal_sql.graph.errors import GraphError


@dataclass(frozen=True)
class JoinStep:
    """One join: following an edge from from_table to edge.target_table."""

    from_table: str
    edge: Edge

    def __post_init__(self) -> None:
        require_text(self.from_table, "from_table")
        if not isinstance(self.edge, Edge):
            raise GraphError(f"not an Edge: {self.edge!r}")

    @property
    def to_table(self) -> str:
        """The table this step joins to."""
        return self.edge.target_table

    def to_join_condition(self) -> str:
        """Return the SQL join condition, one equality per column pair.

        Example: 'orders.customer_id = customers.id', or for a composite key
        'shipments.order_id = order_lines.order_id AND
        shipments.line_no = order_lines.line_no'.
        """
        return " AND ".join(
            f"{self.from_table}.{source} = {self.to_table}.{target}"
            for source, target in self.edge.column_pairs
        )

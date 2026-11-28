"""Settings and checks shared by the join path search of a schema graph."""

from dataclasses import dataclass

from brutal_sql.graph.entity import EdgeType
from brutal_sql.graph.errors import GraphError
from brutal_sql.graph.join_step import JoinStep

DEFAULT_MAX_JOINS = 4


@dataclass(frozen=True)
class PathSearch:
    """Settings shared by every step of one join path search."""

    start_table: str
    max_joins: int
    forward_only: bool


def count_backward_steps(path: list[JoinStep]) -> int:
    """Return how many steps in a join path follow backward edges."""
    return sum(1 for step in path if step.edge.edge_type == EdgeType.BACKWARD)


def require_max_joins(max_joins: int) -> None:
    """Raise GraphError unless max_joins is a positive integer."""
    if isinstance(max_joins, bool) or not isinstance(max_joins, int):
        raise GraphError(f"max_joins must be an integer, got {max_joins!r}")
    if max_joins < 1:
        raise GraphError(f"max_joins must be at least 1, got {max_joins}")

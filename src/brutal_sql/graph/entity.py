"""Plain data classes for entities (tables), their attributes (columns) and edges."""

from dataclasses import dataclass, field
from enum import StrEnum

from brutal_sql.graph.errors import (
    AttributeNotFoundError,
    DuplicateEdgeError,
    EdgeNotFoundError,
    GraphError,
)


def require_text(value: object, field_name: str) -> None:
    """Raise GraphError unless value is a string with non-blank text."""
    if not isinstance(value, str) or not value.strip():
        raise GraphError(f"{field_name} must be a non-blank string, got {value!r}")


class EdgeType(StrEnum):
    """Direction of an edge relative to the foreign key it models."""

    FORWARD = "forward"
    BACKWARD = "backward"


@dataclass(frozen=True)
class EntityAttribute:
    """A column of a table, with a human readable name (e.g. cid -> cookie id)."""

    name: str
    readable_name: str

    def __post_init__(self) -> None:
        require_text(self.name, "name")
        require_text(self.readable_name, "readable_name")


@dataclass(frozen=True)
class Edge:
    """A directed relationship from a column of one entity to a column of another.

    A forward edge goes from the table holding the foreign key to the table it
    references. A backward edge goes the other way.
    """

    source_field: str
    target_table: str
    target_table_field: str
    verb_label: str
    edge_type: EdgeType

    def __post_init__(self) -> None:
        require_text(self.source_field, "source_field")
        require_text(self.target_table, "target_table")
        require_text(self.target_table_field, "target_table_field")
        require_text(self.verb_label, "verb_label")
        if not isinstance(self.edge_type, EdgeType):
            raise GraphError(f"edge_type must be an EdgeType, got {self.edge_type!r}")


@dataclass
class EntityNode:
    """A table in the schema: its name, its attributes and its outgoing edges."""

    name: str
    attributes: list[EntityAttribute]
    edges: list[Edge] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_text(self.name, "name")
        self._check_attributes()
        initial_edges = list(self.edges)
        self.attributes = list(self.attributes)
        self.edges = []
        for edge in initial_edges:
            self.add_edge(edge)

    def _check_attributes(self) -> None:
        """Require at least one attribute, all EntityAttribute, with unique names."""
        if not self.attributes:
            raise GraphError(f"entity {self.name!r} needs at least one attribute")
        for attribute in self.attributes:
            if not isinstance(attribute, EntityAttribute):
                raise GraphError(f"not an EntityAttribute: {attribute!r}")
        names = [attribute.name for attribute in self.attributes]
        if len(names) != len(set(names)):
            raise GraphError(f"entity {self.name!r} has duplicate attribute names")

    def has_attribute(self, attribute_name: str) -> bool:
        """Return True if the entity has an attribute with this name."""
        return any(attribute.name == attribute_name for attribute in self.attributes)

    def add_edge(self, edge: Edge) -> None:
        """Attach an edge that starts at one of this entity's attributes."""
        if not isinstance(edge, Edge):
            raise GraphError(f"not an Edge: {edge!r}")
        if not self.has_attribute(edge.source_field):
            raise AttributeNotFoundError(
                f"entity {self.name!r} has no attribute {edge.source_field!r}"
            )
        if edge in self.edges:
            raise DuplicateEdgeError(f"entity {self.name!r} already has {edge!r}")
        self.edges.append(edge)

    def remove_edge(self, edge: Edge) -> None:
        """Detach an edge; raise EdgeNotFoundError if it is not attached."""
        if edge not in self.edges:
            raise EdgeNotFoundError(f"entity {self.name!r} has no edge {edge!r}")
        self.edges.remove(edge)

    def find_edge(
        self,
        edge_type: EdgeType,
        source_field: str,
        target_table: str,
        target_table_field: str,
    ) -> Edge:
        """Return the edge joining these columns, whatever its verb label."""
        for edge in self.edges:
            if (
                edge.edge_type == edge_type
                and edge.source_field == source_field
                and edge.target_table == target_table
                and edge.target_table_field == target_table_field
            ):
                return edge
        raise EdgeNotFoundError(
            f"entity {self.name!r} has no {edge_type} edge "
            f"{source_field} -> {target_table}.{target_table_field}"
        )

    def remove_edges_to(self, table_name: str) -> list[Edge]:
        """Detach every edge that points at table_name and return them."""
        removed = [edge for edge in self.edges if edge.target_table == table_name]
        self.edges = [edge for edge in self.edges if edge.target_table != table_name]
        return removed

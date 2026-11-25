"""Errors raised when building or querying the schema graph."""


class GraphError(ValueError):
    """Base error for invalid schema graph data or operations."""


class DuplicateNodeError(GraphError):
    """Raised when a node with the same name is already in the graph."""


class NodeNotFoundError(GraphError):
    """Raised when a table name does not match any node in the graph."""


class AttributeNotFoundError(GraphError):
    """Raised when a column name does not match any attribute of a node."""


class DuplicateEdgeError(GraphError):
    """Raised when an identical edge is already attached to a node."""


class EdgeNotFoundError(GraphError):
    """Raised when an edge to remove is not attached to a node."""

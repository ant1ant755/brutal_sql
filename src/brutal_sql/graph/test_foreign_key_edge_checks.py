"""Direct tests for edge_along and the attribute and duplicate-edge checks."""

import pytest

from brutal_sql.graph import (
    AttributeNotFoundError,
    DuplicateEdgeError,
    Edge,
    EdgeType,
    EntityAttribute,
    EntityNode,
    GraphError,
)
from brutal_sql.graph.foreign_key_edges import (
    edge_along,
    require_attribute,
    require_new_edge,
)


def orders() -> EntityNode:
    return EntityNode(
        "orders", [EntityAttribute("id", "id"), EntityAttribute("cid", "customer")]
    )


def placed_by() -> Edge:
    return Edge("cid", "customers", "id", "placed by", EdgeType.FORWARD)


def test_edge_along_carries_edge_id_and_nullable() -> None:
    edge = edge_along(
        [("cid", "id")],
        "customers",
        "placed by",
        EdgeType.FORWARD,
        edge_id="orders_cid_fkey",
        nullable=True,
    )
    assert (edge.edge_id, edge.nullable) == ("orders_cid_fkey", True)


def test_edge_along_rejects_no_pairs() -> None:
    with pytest.raises(GraphError, match="column pair"):
        edge_along([], "customers", "placed by", EdgeType.FORWARD, edge_id="fk")


def test_require_attribute_accepts_existing_column() -> None:
    require_attribute(orders(), "cid")


def test_require_attribute_rejects_missing_column() -> None:
    with pytest.raises(AttributeNotFoundError, match="ghost"):
        require_attribute(orders(), "ghost")


def test_require_new_edge_accepts_unseen_edge() -> None:
    require_new_edge(orders(), placed_by())


def test_require_new_edge_rejects_attached_edge() -> None:
    node = orders()
    node.add_edge(placed_by())
    with pytest.raises(DuplicateEdgeError):
        require_new_edge(node, placed_by())

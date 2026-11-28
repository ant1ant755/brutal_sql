"""Tests for edges that hold every column pair of a composite foreign key."""

import pytest

from brutal_sql.graph import (
    AttributeNotFoundError,
    Edge,
    EdgeType,
    EntityAttribute,
    EntityNode,
    GraphError,
)


def ships_edge(extra: object = (("line_no", "line_no"),)) -> Edge:
    return Edge(
        "order_id", "order_lines", "order_id", "ships", EdgeType.FORWARD, extra
    )  # type: ignore[arg-type]


def shipments_node(columns: list[str]) -> EntityNode:
    return EntityNode("shipments", [EntityAttribute(name, name) for name in columns])


def test_composite_edge_lists_every_pair_in_order() -> None:
    edge = ships_edge((("line_no", "line_no"), ("part", "part_no")))
    assert edge.column_pairs == (
        ("order_id", "order_id"),
        ("line_no", "line_no"),
        ("part", "part_no"),
    )
    assert edge.source_fields == ("order_id", "line_no", "part")
    assert edge.target_fields == ("order_id", "line_no", "part_no")


def test_single_column_edge_has_one_pair_and_equals_old_form() -> None:
    edge = Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)
    assert edge.extra_column_pairs == ()
    assert edge.column_pairs == (("customer_id", "id"),)
    assert edge == Edge(
        "customer_id", "customers", "id", "placed by", EdgeType.FORWARD, ()
    )


def test_composite_edge_differs_from_its_first_pair_alone() -> None:
    assert ships_edge() != ships_edge(())


@pytest.mark.parametrize(
    "extra",
    [
        [("line_no", "line_no")],
        (("line_no",),),
        (("line_no", "line_no", "x"),),
        (("line_no", " "),),
        ((" ", "line_no"),),
        (("line_no", None),),
        ("line_no",),
    ],
)
def test_edge_rejects_malformed_extra_pairs(extra: object) -> None:
    with pytest.raises(GraphError):
        ships_edge(extra)


def test_node_accepts_composite_edge_when_all_columns_exist() -> None:
    node = shipments_node(["id", "order_id", "line_no"])
    node.add_edge(ships_edge())
    assert node.edges == [ships_edge()]


def test_node_rejects_composite_edge_with_missing_extra_column() -> None:
    node = shipments_node(["id", "order_id"])
    with pytest.raises(AttributeNotFoundError, match="line_no"):
        node.add_edge(ships_edge())
    assert node.edges == []

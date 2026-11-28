"""Tests for join conditions of single and composite foreign key edges."""

import pytest

from brutal_sql.graph import Edge, EdgeType, GraphError, JoinStep
from brutal_sql.graph.join_step import JoinStep as JoinStepFromModule

COMPOSITE = Edge(
    "order_id",
    "order_lines",
    "order_id",
    "ships",
    EdgeType.FORWARD,
    (("line_no", "line_no"),),
)


def test_composite_join_condition_joins_every_pair_with_and() -> None:
    step = JoinStep("shipments", COMPOSITE)
    assert step.to_join_condition() == (
        "shipments.order_id = order_lines.order_id"
        " AND shipments.line_no = order_lines.line_no"
    )


def test_single_pair_join_condition_has_no_and() -> None:
    edge = Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)
    condition = JoinStep("orders", edge).to_join_condition()
    assert condition == "orders.customer_id = customers.id"
    assert "AND" not in condition


def test_join_step_is_still_exported_from_graph_package() -> None:
    assert JoinStep is JoinStepFromModule


@pytest.mark.parametrize("edge", [None, "order_lines", ("order_id", "order_id")])
def test_join_step_rejects_non_edge(edge: object) -> None:
    with pytest.raises(GraphError, match="not an Edge"):
        JoinStep("shipments", edge)  # type: ignore[arg-type]

"""Tests for entity attributes, edges and entity nodes."""

import pytest

from brutal_sql.graph.entity import (
    Edge,
    EdgeType,
    EntityAttribute,
    EntityNode,
    require_text,
)
from brutal_sql.graph.errors import (
    AttributeNotFoundError,
    DuplicateEdgeError,
    EdgeNotFoundError,
    GraphError,
)


def make_attribute(name: str) -> EntityAttribute:
    return EntityAttribute(name, name.replace("_", " "))


def make_customers() -> EntityNode:
    columns = ["id", "name", "address", "age"]
    return EntityNode("customers", [make_attribute(column) for column in columns])


def placed_by_edge() -> Edge:
    return Edge("customer_id", "customers", "id", "placed by", EdgeType.FORWARD)


def make_orders(edges: list[Edge] | None = None) -> EntityNode:
    columns = ["id", "billing_amount", "customer_id", "order_status"]
    attributes = [make_attribute(column) for column in columns]
    return EntityNode("orders", attributes, edges or [])


# require_text


def test_require_text_accepts_non_blank_string() -> None:
    require_text("orders", "name")


@pytest.mark.parametrize("value", ["", "   ", None, 7])
def test_require_text_rejects_blank_or_non_string(value: object) -> None:
    with pytest.raises(GraphError, match="name must be a non-blank string"):
        require_text(value, "name")


# EntityAttribute


def test_entity_attribute_keeps_name_and_readable_name() -> None:
    attribute = EntityAttribute("cid", "cookie id")
    assert attribute.name == "cid"
    assert attribute.readable_name == "cookie id"


@pytest.mark.parametrize("name, readable_name", [("", "cookie id"), ("cid", " ")])
def test_entity_attribute_rejects_blank_fields(name: str, readable_name: str) -> None:
    with pytest.raises(GraphError):
        EntityAttribute(name, readable_name)


# Edge


def test_edge_keeps_its_fields_and_is_hashable() -> None:
    edge = placed_by_edge()
    assert edge.source_field == "customer_id"
    assert edge.target_table == "customers"
    assert edge.target_table_field == "id"
    assert edge.verb_label == "placed by"
    assert edge.edge_type is EdgeType.FORWARD
    assert edge in {placed_by_edge()}


def test_edge_rejects_blank_verb_label() -> None:
    with pytest.raises(GraphError, match="verb_label"):
        Edge("customer_id", "customers", "id", "", EdgeType.FORWARD)


def test_edge_rejects_edge_type_that_is_not_an_edge_type() -> None:
    with pytest.raises(GraphError, match="edge_type"):
        Edge("customer_id", "customers", "id", "placed by", "sideways")


# EntityNode


def test_entity_node_keeps_name_attributes_and_edges() -> None:
    customers = make_customers()
    assert customers.name == "customers"
    assert [attribute.name for attribute in customers.attributes] == [
        "id",
        "name",
        "address",
        "age",
    ]
    assert customers.edges == []
    orders = make_orders([placed_by_edge()])
    assert orders.edges == [placed_by_edge()]


def test_entity_node_rejects_empty_attribute_list() -> None:
    with pytest.raises(GraphError, match="at least one attribute"):
        EntityNode("customers", [])


def test_entity_node_rejects_duplicate_attribute_names() -> None:
    with pytest.raises(GraphError, match="duplicate attribute"):
        EntityNode("customers", [make_attribute("id"), make_attribute("id")])


def test_entity_node_rejects_blank_name() -> None:
    with pytest.raises(GraphError, match="name"):
        EntityNode(" ", [make_attribute("id")])


def test_entity_node_rejects_attribute_of_wrong_type() -> None:
    with pytest.raises(GraphError, match="not an EntityAttribute"):
        EntityNode("customers", ["id"])


def test_entity_node_rejects_initial_edge_on_unknown_column() -> None:
    edge = Edge("missing", "customers", "id", "placed by", EdgeType.FORWARD)
    with pytest.raises(AttributeNotFoundError):
        make_orders([edge])


def test_has_attribute_is_true_only_for_existing_columns() -> None:
    customers = make_customers()
    assert customers.has_attribute("age")
    assert not customers.has_attribute("salary")


def test_add_edge_attaches_edge() -> None:
    orders = make_orders()
    orders.add_edge(placed_by_edge())
    assert orders.edges == [placed_by_edge()]


def test_add_edge_rejects_duplicate_edge() -> None:
    orders = make_orders([placed_by_edge()])
    with pytest.raises(DuplicateEdgeError):
        orders.add_edge(placed_by_edge())


def test_add_edge_rejects_edge_from_unknown_column() -> None:
    edge = Edge("cust", "customers", "id", "placed by", EdgeType.FORWARD)
    with pytest.raises(AttributeNotFoundError):
        make_orders().add_edge(edge)


def test_add_edge_rejects_non_edge() -> None:
    with pytest.raises(GraphError, match="not an Edge"):
        make_orders().add_edge("customers")


def test_remove_edge_detaches_edge() -> None:
    orders = make_orders([placed_by_edge()])
    orders.remove_edge(placed_by_edge())
    assert orders.edges == []


def test_remove_edge_rejects_missing_edge() -> None:
    with pytest.raises(EdgeNotFoundError):
        make_orders().remove_edge(placed_by_edge())


def test_find_edge_matches_columns_and_type() -> None:
    orders = make_orders([placed_by_edge()])
    found = orders.find_edge(EdgeType.FORWARD, "customer_id", "customers", "id")
    assert found == placed_by_edge()


def test_find_edge_rejects_wrong_edge_type() -> None:
    orders = make_orders([placed_by_edge()])
    with pytest.raises(EdgeNotFoundError):
        orders.find_edge(EdgeType.BACKWARD, "customer_id", "customers", "id")


def test_remove_edges_to_drops_only_edges_to_that_table() -> None:
    other = Edge("id", "order_items", "order_id", "contains", EdgeType.BACKWARD)
    orders = make_orders([placed_by_edge(), other])
    assert orders.remove_edges_to("customers") == [placed_by_edge()]
    assert orders.edges == [other]


def test_remove_edges_to_unlinked_table_removes_nothing() -> None:
    orders = make_orders([placed_by_edge()])
    assert orders.remove_edges_to("products") == []
    assert orders.edges == [placed_by_edge()]

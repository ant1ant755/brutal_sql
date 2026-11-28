"""Tests for the ontology validator: types, verbs and role names."""

import dataclasses

import pytest

from brutal_sql.graph import (
    EdgeType,
    EntityAttribute,
    EntityNode,
    Graph,
    GraphError,
    OntologyError,
    TableType,
    apply_annotations,
    find_ontology_problems,
    validate_ontology,
)
from brutal_sql.graph.test_annotations_apply import complete_annotations
from brutal_sql.graph.test_annotations_draft import make_orders_graph


def annotated_graph() -> Graph:
    return apply_annotations(make_orders_graph(), complete_annotations())


def graph_with(edit: str, value: object = None) -> Graph:
    annotations = complete_annotations()
    if edit == "type":
        annotations["tables"]["address"]["type"] = "TODO"
    elif edit in ("verb_forward", "verb_backward", "role_name"):
        annotations["edges"]["orders_billing_fkey"][edit] = value
    return apply_annotations(make_orders_graph(), annotations)


def problems_of(graph: Graph) -> list[str]:
    with pytest.raises(OntologyError) as caught:
        validate_ontology(graph)
    assert str(caught.value).count("\n- ") == len(caught.value.problems)
    return caught.value.problems


def test_fully_annotated_graph_passes() -> None:
    graph = annotated_graph()
    assert validate_ontology(graph) is None
    assert find_ontology_problems(graph) == []


def test_todo_type_is_reported_with_its_table() -> None:
    assert problems_of(graph_with("type")) == ["table 'address' has no table type"]


def test_missing_forward_verb_is_reported_with_its_edge_id() -> None:
    assert problems_of(graph_with("verb_forward", "TODO")) == [
        "edge 'orders_billing_fkey' (orders -> address) has no forward verb"
    ]


def test_missing_backward_verb_is_reported_with_its_edge_id() -> None:
    assert problems_of(graph_with("verb_backward", "TODO")) == [
        "edge 'orders_billing_fkey' (address -> orders) has no backward verb"
    ]


def test_same_table_foreign_keys_without_role_names_are_each_reported() -> None:
    annotations = complete_annotations()
    for edge_id in ("orders_billing_fkey", "orders_shipping_fkey"):
        annotations["edges"][edge_id]["role_name"] = None
    problems = problems_of(apply_annotations(make_orders_graph(), annotations))
    assert problems == [
        f"edge '{edge_id}' (orders -> address) needs a role name: "
        "2 foreign keys join these tables"
        for edge_id in ("orders_billing_fkey", "orders_shipping_fkey")
    ]


def test_repeated_role_name_is_reported() -> None:
    problems = problems_of(graph_with("role_name", "shipping"))
    assert problems == [
        "role name 'shipping' is used by more than one foreign key "
        "(orders -> address)"
    ]


def test_single_foreign_key_between_two_tables_needs_no_role_name() -> None:
    graph = annotated_graph()
    edge = graph.get_node("orders").find_edge(
        EdgeType.FORWARD, "customer_id", "customer", "id"
    )
    assert edge.role_name is None
    assert find_ontology_problems(graph) == []


def test_unannotated_graph_lists_every_problem_in_one_error() -> None:
    problems = problems_of(make_orders_graph())
    assert len(problems) == 3 + 6 + 2
    assert problems[0] == "table 'customer' has no table type"
    assert any("orders_customer_fkey" in problem for problem in problems)


def test_edge_without_edge_id_is_named_by_its_columns() -> None:
    customer = EntityNode("customer", [EntityAttribute("id", "id")])
    orders = EntityNode(
        "orders",
        [EntityAttribute("id", "id"), EntityAttribute("customer_id", "c")],
    )
    graph = Graph("shop", [customer, orders])
    graph.add_foreign_key("orders", "customer_id", "customer", "id", "x", "y")
    for node in graph.nodes:
        node.table_type = TableType.ENTITY
    edge = graph.get_node("orders").edges[0]
    graph.get_node("orders").edges[0] = dataclasses.replace(
        edge, verb_label="references"
    )
    assert problems_of(graph) == [
        "edge orders(customer_id) -> customer(id) (orders -> customer) "
        "has no forward verb"
    ]


def test_find_ontology_problems_rejects_non_graph() -> None:
    with pytest.raises(GraphError, match="not a Graph"):
        find_ontology_problems("shop")  # type: ignore[arg-type]


def test_ontology_error_is_a_graph_error() -> None:
    assert issubclass(OntologyError, GraphError)

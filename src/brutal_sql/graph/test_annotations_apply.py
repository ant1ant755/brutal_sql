"""Tests for applying an ontology annotations file to a schema graph."""

from typing import Any

import pytest

from brutal_sql.graph import (
    TODO_MARKER,
    AnnotationError,
    EdgeType,
    EntityAttribute,
    EntityNode,
    Graph,
    TableType,
    apply_annotations,
    draft_annotations,
)
from brutal_sql.graph.test_annotations_draft import make_orders_graph, make_staff_graph

VERBS = {
    "orders_customer_fkey": ("placed by", "places", None),
    "orders_billing_fkey": ("billed to", "receives bills for", "billing"),
    "orders_shipping_fkey": ("shipped to", "receives", "shipping"),
}
TYPES = {"customer": "entity", "address": "dimension", "orders": "entity"}


def complete_annotations() -> dict[str, Any]:
    annotations = draft_annotations(make_orders_graph())
    for table_name, table_type in TYPES.items():
        annotations["tables"][table_name]["type"] = table_type
    for edge_id, (forward, backward, role_name) in VERBS.items():
        annotations["edges"][edge_id].update(
            verb_forward=forward, verb_backward=backward, role_name=role_name
        )
    return annotations


def edge_labels(graph: Graph) -> dict[tuple[str, EdgeType], tuple[str, str | None]]:
    return {
        (edge.edge_id, edge.edge_type): (edge.verb_label, edge.role_name)
        for node in graph.nodes
        for edge in node.edges
    }


def test_complete_file_sets_every_type_and_both_verbs() -> None:
    graph = apply_annotations(make_orders_graph(), complete_annotations())
    assert {node.name: node.table_type for node in graph.nodes} == {
        name: TableType(value) for name, value in TYPES.items()
    }
    expected = {}
    for edge_id, (forward, backward, role_name) in VERBS.items():
        expected[(edge_id, EdgeType.FORWARD)] = (forward, role_name)
        expected[(edge_id, EdgeType.BACKWARD)] = (backward, role_name)
    assert edge_labels(graph) == expected


def test_apply_leaves_the_input_graph_unchanged() -> None:
    graph = make_orders_graph()
    before = graph.to_json()
    apply_annotations(graph, complete_annotations())
    assert graph.to_json() == before


def test_annotated_graph_keeps_join_columns_and_identity() -> None:
    graph = make_orders_graph()
    annotated = apply_annotations(graph, complete_annotations())
    for before, after in zip(graph.nodes, annotated.nodes):
        assert [edge.column_pairs for edge in before.edges] == [
            edge.column_pairs for edge in after.edges
        ]
        assert [edge.edge_id for edge in before.edges] == [
            edge.edge_id for edge in after.edges
        ]


def test_todo_values_and_missing_entries_keep_the_placeholders() -> None:
    annotations = draft_annotations(make_orders_graph())
    annotations["tables"]["orders"]["type"] = "entity"
    del annotations["tables"]["customer"]
    annotations["edges"]["orders_billing_fkey"]["verb_forward"] = "billed to"
    del annotations["edges"]["orders_customer_fkey"]
    graph = apply_annotations(make_orders_graph(), annotations)
    types = {node.name: node.table_type for node in graph.nodes}
    assert types == {"customer": None, "address": None, "orders": TableType.ENTITY}
    labels = edge_labels(graph)
    assert labels[("orders_billing_fkey", EdgeType.FORWARD)] == ("billed to", None)
    assert labels[("orders_billing_fkey", EdgeType.BACKWARD)] == (
        "referenced by",
        None,
    )
    assert labels[("orders_customer_fkey", EdgeType.FORWARD)] == ("references", None)


def test_mirror_table_and_its_edge_can_be_annotated() -> None:
    annotations = draft_annotations(make_staff_graph())
    annotations["tables"]["managers"]["type"] = "entity"
    annotations["edges"]["employee_manager_id_fkey"].update(
        verb_forward="reports to", verb_backward="manages", role_name=None
    )
    graph = apply_annotations(make_staff_graph(), annotations)
    managers = graph.get_node("managers")
    assert managers.is_mirror
    assert managers.table_type is TableType.ENTITY
    assert managers.edges[0].verb_label == "manages"
    assert graph.get_node("employee").edges[0].verb_label == "reports to"


def test_apply_rejects_an_unknown_table() -> None:
    annotations = complete_annotations()
    annotations["tables"]["invoices"] = {"type": "entity"}
    with pytest.raises(AnnotationError, match="unknown table 'invoices'"):
        apply_annotations(make_orders_graph(), annotations)


def test_apply_rejects_an_unknown_edge_id() -> None:
    annotations = complete_annotations()
    annotations["edges"]["orders_invoice_fkey"] = dict(
        annotations["edges"]["orders_customer_fkey"]
    )
    with pytest.raises(AnnotationError, match="unknown edge_id 'orders_invoice_fkey'"):
        apply_annotations(make_orders_graph(), annotations)


@pytest.mark.parametrize("bad_type", ["fact", "Entity", "", None, 3])
def test_apply_rejects_an_invalid_type_value(bad_type: object) -> None:
    annotations = complete_annotations()
    annotations["tables"]["orders"]["type"] = bad_type
    with pytest.raises(AnnotationError, match="'orders' has invalid type"):
        apply_annotations(make_orders_graph(), annotations)


def test_apply_rejects_a_table_entry_without_type() -> None:
    annotations = complete_annotations()
    annotations["tables"]["orders"] = {}
    with pytest.raises(AnnotationError, match="needs a 'type' key"):
        apply_annotations(make_orders_graph(), annotations)


def test_apply_rejects_a_file_for_another_schema() -> None:
    annotations = complete_annotations()
    annotations["schema_name"] = "warehouse"
    with pytest.raises(AnnotationError, match="for schema 'warehouse'"):
        apply_annotations(make_orders_graph(), annotations)


def test_apply_rejects_an_edge_whose_tables_do_not_match() -> None:
    annotations = complete_annotations()
    annotations["edges"]["orders_billing_fkey"]["to_table"] = "customer"
    with pytest.raises(AnnotationError, match="joins 'orders' -> 'address'"):
        apply_annotations(make_orders_graph(), annotations)


def test_apply_rejects_an_edge_entry_missing_keys() -> None:
    annotations = complete_annotations()
    del annotations["edges"]["orders_billing_fkey"]["role_name"]
    with pytest.raises(AnnotationError, match="missing \\['role_name'\\]"):
        apply_annotations(make_orders_graph(), annotations)


@pytest.mark.parametrize(
    "key, value",
    [("verb_forward", ""), ("verb_backward", None), ("role_name", "  ")],
)
def test_apply_rejects_blank_verbs_and_role_names(key: str, value: object) -> None:
    annotations = complete_annotations()
    annotations["edges"]["orders_billing_fkey"][key] = value
    with pytest.raises(AnnotationError, match=key):
        apply_annotations(make_orders_graph(), annotations)


def test_bad_file_applies_nothing() -> None:
    graph = make_orders_graph()
    before = graph.to_json()
    annotations = complete_annotations()
    annotations["edges"]["orders_shipping_fkey"]["verb_forward"] = ""
    with pytest.raises(AnnotationError):
        apply_annotations(graph, annotations)
    assert graph.to_json() == before
    assert TODO_MARKER not in before


def test_composite_foreign_key_keeps_every_column_pair_when_annotated() -> None:
    lines = EntityNode(
        "order_lines", [EntityAttribute(name, name) for name in ("order_id", "line")]
    )
    shipments = EntityNode(
        "shipments", [EntityAttribute(name, name) for name in ("order_id", "line")]
    )
    graph = Graph("lines", [lines, shipments])
    graph.add_composite_foreign_key(
        "shipments",
        ["order_id", "line"],
        "order_lines",
        ["order_id", "line"],
        "references",
        "referenced by",
        edge_id="shipments_line_fkey",
    )
    annotations = draft_annotations(graph)
    annotations["edges"]["shipments_line_fkey"].update(
        verb_forward="ships", verb_backward="shipped in", role_name=None
    )
    annotated = apply_annotations(graph, annotations)
    edge = annotated.get_node("shipments").edges[0]
    assert edge.verb_label == "ships"
    assert edge.column_pairs == (("order_id", "order_id"), ("line", "line"))
    assert annotated.get_node("order_lines").edges[0].verb_label == "shipped in"

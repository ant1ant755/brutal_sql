"""Tests for drafting ontology annotations and reading them back from JSON."""

import json

import pytest

from brutal_sql.graph import (
    TODO_MARKER,
    AnnotationError,
    EntityAttribute,
    EntityNode,
    Graph,
    MirrorSource,
    annotations_from_json,
    annotations_to_json,
    draft_annotations,
)


def make_orders_graph() -> Graph:
    customer = EntityNode("customer", [EntityAttribute("id", "id")])
    address = EntityNode("address", [EntityAttribute("id", "id")])
    columns = ("id", "customer_id", "billing_address_id", "shipping_address_id")
    orders = EntityNode("orders", [EntityAttribute(name, name) for name in columns])
    graph = Graph("shop", [customer, address, orders])
    for column, target, edge_id in [
        ("customer_id", "customer", "orders_customer_fkey"),
        ("billing_address_id", "address", "orders_billing_fkey"),
        ("shipping_address_id", "address", "orders_shipping_fkey"),
    ]:
        graph.add_foreign_key(
            "orders",
            column,
            target,
            "id",
            "references",
            "referenced by",
            edge_id=edge_id,
        )
    return graph


def make_staff_graph() -> Graph:
    employee = EntityNode(
        "employee", [EntityAttribute(name, name) for name in ("id", "manager_id")]
    )
    managers = EntityNode(
        "managers",
        [EntityAttribute("id", "id")],
        mirror_of=MirrorSource("employee", "manager_id", "id", (("id", "id"),)),
    )
    graph = Graph("staff", [employee, managers])
    graph.add_foreign_key(
        "employee",
        "manager_id",
        "managers",
        "id",
        "references",
        "referenced by",
        edge_id="employee_manager_id_fkey",
    )
    return graph


def test_draft_lists_every_table_and_edge_id_as_todo() -> None:
    draft = draft_annotations(make_orders_graph())
    assert draft["format_version"] == 1
    assert draft["schema_name"] == "shop"
    assert draft["tables"] == {
        name: {"type": TODO_MARKER} for name in ("customer", "address", "orders")
    }
    assert set(draft["edges"]) == {
        "orders_customer_fkey",
        "orders_billing_fkey",
        "orders_shipping_fkey",
    }
    assert draft["edges"]["orders_billing_fkey"] == {
        "from_table": "orders",
        "to_table": "address",
        "verb_forward": TODO_MARKER,
        "verb_backward": TODO_MARKER,
        "role_name": TODO_MARKER,
    }


def test_draft_includes_mirror_tables_and_their_edge() -> None:
    draft = draft_annotations(make_staff_graph())
    assert set(draft["tables"]) == {"employee", "managers"}
    entry = draft["edges"]["employee_manager_id_fkey"]
    assert (entry["from_table"], entry["to_table"]) == ("employee", "managers")


def test_draft_rejects_an_edge_without_edge_id() -> None:
    graph = make_orders_graph()
    graph.add_foreign_key("customer", "id", "address", "id", "a", "b")
    with pytest.raises(AnnotationError, match="has no edge_id"):
        draft_annotations(graph)


def test_draft_rejects_two_foreign_keys_sharing_an_edge_id() -> None:
    graph = make_orders_graph()
    graph.add_foreign_key(
        "customer", "id", "address", "id", "a", "b", edge_id="orders_customer_fkey"
    )
    with pytest.raises(AnnotationError, match="more than one foreign key"):
        draft_annotations(graph)


def test_draft_round_trips_through_json() -> None:
    draft = draft_annotations(make_orders_graph())
    text = annotations_to_json(draft)
    assert json.loads(text) == draft
    assert annotations_from_json(text) == draft


def test_annotations_from_json_rejects_invalid_json() -> None:
    with pytest.raises(AnnotationError, match="invalid annotations JSON"):
        annotations_from_json("{not json")


def test_annotations_from_json_rejects_non_text() -> None:
    with pytest.raises(AnnotationError, match="must be a string"):
        annotations_from_json(b"{}")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "data, message",
    [
        ([], "must be a dict"),
        ({"format_version": 2}, "unsupported annotations format"),
        ({"format_version": 1, "tables": {}, "edges": {}}, "schema_name"),
        ({"format_version": 1, "schema_name": "shop", "edges": {}}, "'tables'"),
        ({"format_version": 1, "schema_name": "shop", "tables": {}}, "'edges'"),
    ],
)
def test_annotations_from_json_rejects_a_malformed_file(
    data: object, message: str
) -> None:
    with pytest.raises(AnnotationError, match=message):
        annotations_from_json(json.dumps(data))

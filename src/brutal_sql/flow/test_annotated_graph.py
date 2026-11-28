"""Unit tests for building and validating an annotated graph (no database)."""

import importlib
import logging
from typing import Any

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.errors import ProcessingError
from brutal_sql.flow import BACKWARD_VERB, FORWARD_VERB, build_annotated_graph
from brutal_sql.flow.self_reference import MIRROR_BACKWARD_VERB, MIRROR_FORWARD_VERB
from brutal_sql.graph import (
    PLACEHOLDER_VERBS,
    AnnotationError,
    Graph,
    OntologyError,
    TableType,
)
from brutal_sql.graph.test_annotations_apply import complete_annotations
from brutal_sql.graph.test_annotations_draft import make_orders_graph

flow_module = importlib.import_module("brutal_sql.flow.annotated_graph")
USER = "ontologyuserxyz"
PASSWORD = "ontologypasswordxyz"
SETTINGS = ConnectionSettings("db.local", 5432, "shop_db", "shop", USER, PASSWORD)


@pytest.fixture(autouse=True)
def stub_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        flow_module, "fetch_schema_graph", lambda _: make_orders_graph()
    )


def failure_of(annotations: dict[str, Any], caplog: pytest.LogCaptureFixture) -> str:
    with caplog.at_level(logging.DEBUG), pytest.raises(ProcessingError) as caught:
        build_annotated_graph(SETTINGS, annotations)
    texts = [str(caught.value), repr(caught.value), caplog.text]
    texts.append(str(caught.value.__cause__))
    leaked = any(secret in text for secret in (USER, PASSWORD) for text in texts)
    assert not leaked, "error text or logs leak a database username or password"
    return str(caught.value)


def test_complete_annotations_give_a_validated_graph() -> None:
    graph = build_annotated_graph(SETTINGS, complete_annotations())
    assert isinstance(graph, Graph)
    assert graph.get_node("orders").table_type is TableType.ENTITY


def test_incomplete_ontology_lists_every_problem(
    caplog: pytest.LogCaptureFixture,
) -> None:
    annotations = complete_annotations()
    annotations["tables"]["address"]["type"] = "TODO"
    annotations["edges"]["orders_billing_fkey"]["verb_forward"] = "TODO"
    message = failure_of(annotations, caplog)
    assert "db.local:5432/shop_db" in message
    assert "table 'address' has no table type" in message
    assert "'orders_billing_fkey' (orders -> address) has no forward verb" in message


def test_incomplete_ontology_chains_the_ontology_error() -> None:
    annotations = complete_annotations()
    annotations["tables"]["address"]["type"] = "TODO"
    with pytest.raises(ProcessingError) as caught:
        build_annotated_graph(SETTINGS, annotations)
    assert isinstance(caught.value.__cause__, OntologyError)


def test_bad_annotations_raise_processing_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    annotations = complete_annotations()
    annotations["tables"]["invoices"] = {"type": "entity"}
    message = failure_of(annotations, caplog)
    assert "unknown table 'invoices'" in message


def test_bad_annotations_chain_the_annotation_error() -> None:
    with pytest.raises(ProcessingError) as caught:
        build_annotated_graph(SETTINGS, {"format_version": 2})
    assert isinstance(caught.value.__cause__, AnnotationError)


def test_flow_placeholder_verbs_count_as_missing_verbs() -> None:
    placeholders = {FORWARD_VERB, BACKWARD_VERB, MIRROR_FORWARD_VERB}
    placeholders.add(MIRROR_BACKWARD_VERB)
    assert placeholders <= PLACEHOLDER_VERBS

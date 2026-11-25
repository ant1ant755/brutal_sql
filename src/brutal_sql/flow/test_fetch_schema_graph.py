"""Unit tests for the fetch-then-convert flow (no database)."""

import importlib

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.db.table_metadata import ColumnMetadata, TableMetadata
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.fetch_schema_graph import count_edges, fetch_schema_graph
from brutal_sql.flow.schema_to_graph import convert_tables_to_graph

# The package re-exports a function of the same name, so load the module itself.
flow_module = importlib.import_module("brutal_sql.flow.fetch_schema_graph")


def one_table() -> list[TableMetadata]:
    return [TableMetadata("customers", (ColumnMetadata("id", "INTEGER"),))]


def test_fetch_schema_graph_converts_fetched_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow_module, "fetch_schema_tables", lambda _: one_table())
    settings = ConnectionSettings("db.local", 5432, "shop", "public")
    graph = fetch_schema_graph(settings)
    assert graph.schema_name == "public"
    assert [node.name for node in graph.nodes] == ["customers"]


def test_fetch_schema_graph_rejects_non_settings() -> None:
    with pytest.raises(ProcessingError):
        fetch_schema_graph("postgresql://db.local/shop")  # type: ignore[arg-type]


def test_count_edges_counts_zero_for_graph_without_keys() -> None:
    assert count_edges(convert_tables_to_graph("public", one_table())) == 0


def test_count_edges_rejects_non_graph() -> None:
    with pytest.raises(AttributeError):
        count_edges(None)  # type: ignore[arg-type]

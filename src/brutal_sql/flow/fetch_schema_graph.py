"""Fetch a Postgres schema and build its entity graph in one call."""

import logging

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.db.postgres_fetcher import fetch_schema_tables
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.schema_to_graph import convert_tables_to_graph
from brutal_sql.graph import Graph

logger = logging.getLogger(__name__)


def count_edges(graph: Graph) -> int:
    """Return the number of edges (forward and backward) across all nodes."""
    return sum(len(node.edges) for node in graph.nodes)


def fetch_schema_graph(settings: ConnectionSettings) -> Graph:
    """Read every table of settings.schema_name and return its entity graph.

    Raises ProcessingError if the database can't be read or the graph is invalid.
    """
    if not isinstance(settings, ConnectionSettings):
        raise ProcessingError("settings must be ConnectionSettings")
    tables = fetch_schema_tables(settings)
    graph = convert_tables_to_graph(settings.schema_name, tables)
    logger.info(
        "Built entity graph of %r on %s: %d nodes, %d edges",
        settings.schema_name,
        settings.describe_database(),
        len(graph.nodes),
        count_edges(graph),
    )
    return graph

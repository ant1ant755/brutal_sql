"""Build a schema's annotated graph and check its ontology in one call."""

import logging
from typing import Any

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.fetch_schema_graph import fetch_schema_graph
from brutal_sql.graph import Graph, GraphError, apply_annotations
from brutal_sql.graph.ontology_validator import validate_ontology

logger = logging.getLogger(__name__)


def build_annotated_graph(
    settings: ConnectionSettings, annotations: dict[str, Any]
) -> Graph:
    """Fetch the schema graph, apply the annotations and validate the ontology.

    Returns the annotated graph. Raises ProcessingError if the schema can't be
    read, the annotations don't fit the graph, or the ontology is incomplete.
    The error lists every problem and names the database only by host, port and
    database name.
    """
    graph = fetch_schema_graph(settings)
    try:
        annotated = apply_annotations(graph, annotations)
        validate_ontology(annotated)
    except GraphError as error:
        raise ProcessingError(
            f"ontology of schema {settings.schema_name!r} on "
            f"{settings.describe_database()} is not ready: {error}"
        ) from error
    logger.info(
        "Ontology of %r on %s is complete",
        settings.schema_name,
        settings.describe_database(),
    )
    return annotated

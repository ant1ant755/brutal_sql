"""Graph ontology of a database schema: entities, attributes and join edges."""

from brutal_sql.graph.annotation_apply import apply_annotations
from brutal_sql.graph.annotations import (
    TODO_MARKER,
    AnnotationError,
    annotations_from_json,
    annotations_to_json,
    draft_annotations,
)
from brutal_sql.graph.entity import (
    Edge,
    EdgeType,
    EntityAttribute,
    EntityNode,
    TableType,
)
from brutal_sql.graph.errors import (
    AttributeNotFoundError,
    DuplicateEdgeError,
    DuplicateNodeError,
    EdgeNotFoundError,
    GraphError,
    NodeNotFoundError,
)
from brutal_sql.graph.join_tree import JoinTree, JoinTreeError, JoinType, TreeEdge
from brutal_sql.graph.mirror import MirrorSource, RowFilter
from brutal_sql.graph.ontology_validator import (
    PLACEHOLDER_VERBS,
    OntologyError,
    find_ontology_problems,
    validate_ontology,
)
from brutal_sql.graph.schema_graph import Graph, JoinStep
from brutal_sql.graph.serialization import (
    graph_from_dict,
    graph_from_json,
    graph_to_dict,
    graph_to_json,
)

__all__ = [
    "AnnotationError",
    "AttributeNotFoundError",
    "DuplicateEdgeError",
    "DuplicateNodeError",
    "Edge",
    "EdgeNotFoundError",
    "EdgeType",
    "EntityAttribute",
    "EntityNode",
    "Graph",
    "GraphError",
    "JoinStep",
    "JoinTree",
    "JoinTreeError",
    "JoinType",
    "MirrorSource",
    "NodeNotFoundError",
    "OntologyError",
    "PLACEHOLDER_VERBS",
    "RowFilter",
    "TODO_MARKER",
    "TableType",
    "TreeEdge",
    "annotations_from_json",
    "annotations_to_json",
    "apply_annotations",
    "draft_annotations",
    "find_ontology_problems",
    "graph_from_dict",
    "graph_from_json",
    "graph_to_dict",
    "graph_to_json",
    "validate_ontology",
]

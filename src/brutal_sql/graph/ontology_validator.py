"""Check that a schema graph's ontology is complete before join trees are built.

Complete means: every node has a table type; every edge has a real verb (not a
placeholder such as "references" / "referenced by", and not TODO); and foreign
keys that go from the same table to the same table have distinct role names
(e.g. orders -> address as "billing" and "shipping").
"""

from collections import defaultdict

from brutal_sql.graph.annotations import TODO_MARKER
from brutal_sql.graph.entity import Edge, EdgeType, EntityNode
from brutal_sql.graph.errors import GraphError
from brutal_sql.graph.schema_graph import Graph

PLACEHOLDER_VERBS = frozenset({"references", "referenced by", TODO_MARKER})


class OntologyError(GraphError):
    """Raised when the ontology is incomplete; problems lists every gap found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        listed = "\n".join(f"- {problem}" for problem in self.problems)
        super().__init__(f"ontology is incomplete:\n{listed}")


def _describe_edge(node_name: str, edge: Edge) -> str:
    """Name an edge by its edge_id, or by its columns when it has none."""
    if edge.edge_id is not None:
        return f"edge {edge.edge_id!r}"
    sources = ",".join(edge.source_fields)
    targets = ",".join(edge.target_fields)
    return f"edge {node_name}({sources}) -> {edge.target_table}({targets})"


def find_ontology_problems(graph: Graph) -> list[str]:
    """Return every gap in the graph's ontology; an empty list means complete."""
    if not isinstance(graph, Graph):
        raise GraphError(f"not a Graph: {graph!r}")
    problems = [
        f"table {node.name!r} has no table type"
        for node in graph.nodes
        if node.table_type is None
    ]
    for node in graph.nodes:
        problems.extend(_verb_problems(node))
    problems.extend(_role_name_problems(graph))
    return problems


def validate_ontology(graph: Graph) -> None:
    """Return if the ontology is complete; raise OntologyError listing every gap."""
    problems = find_ontology_problems(graph)
    if problems:
        raise OntologyError(problems)


def _verb_problems(node: EntityNode) -> list[str]:
    """Report each edge of node whose verb is still a placeholder."""
    problems = []
    for edge in node.edges:
        if edge.verb_label.strip() not in PLACEHOLDER_VERBS:
            continue
        direction = "forward" if edge.edge_type == EdgeType.FORWARD else "backward"
        problems.append(
            f"{_describe_edge(node.name, edge)} ({node.name} -> {edge.target_table}) "
            f"has no {direction} verb"
        )
    return problems


def _role_name_problems(graph: Graph) -> list[str]:
    """Report foreign keys between the same two tables without distinct roles."""
    groups: dict[tuple[str, str], list[Edge]] = defaultdict(list)
    for node in graph.nodes:
        for edge in node.edges:
            if edge.edge_type == EdgeType.FORWARD:
                groups[(node.name, edge.target_table)].append(edge)
    problems = []
    for (source, target), edges in groups.items():
        if len(edges) > 1:
            problems.extend(_group_role_problems(source, target, edges))
    return problems


def _group_role_problems(source: str, target: str, edges: list[Edge]) -> list[str]:
    """Report missing and repeated role names among foreign keys source -> target."""
    tables = f"{source} -> {target}"
    problems = [
        f"{_describe_edge(source, edge)} ({tables}) needs a role name: "
        f"{len(edges)} foreign keys join these tables"
        for edge in edges
        if edge.role_name is None
    ]
    role_names = [edge.role_name for edge in edges if edge.role_name is not None]
    for role_name in sorted(
        {name for name in role_names if role_names.count(name) > 1}
    ):
        problems.append(
            f"role name {role_name!r} is used by more than one foreign key ({tables})"
        )
    return problems

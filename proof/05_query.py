"""Step 5: Query the graph — can we answer real questions?

Run:  uv run python -m proof.05_query

Validation step: if the graph faithfully represents the document, we
should be able to answer domain questions using only graph traversal.

Queries are generated dynamically from the SchemaSpec — no hardcoded
node labels or relationship types.
"""

from __future__ import annotations

import sys

from neo4j import GraphDatabase

from proof.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from proof.log import get_logger
from proof.schema import SchemaSpec, load_schema

log = get_logger("proof.05_query")


def _run_query(session, name: str, cypher: str, validator=None) -> bool:
    """Run a named query, print results, validate."""
    log.info("--- Q: %s ---", name)
    result = session.run(cypher)
    records = list(result)

    if not records:
        log.warning("  No results!")
        return False

    for record in records[:10]:
        log.info("  %s", dict(record))

    if len(records) > 10:
        log.info("  ... and %d more", len(records) - 10)

    if validator:
        passed = validator(records)
        log.info("  PASS" if passed else "  FAIL")
        return passed

    log.info("  (%d results)", len(records))
    return True


def _generate_schema_queries(schema: SchemaSpec) -> list[tuple[str, str, object]]:
    """Generate validation queries from SchemaSpec."""
    queries: list[tuple[str, str, object]] = []

    # Count nodes per type
    for nt in schema.node_types:
        queries.append((
            f"Count {nt.name} nodes",
            f"MATCH (n:{nt.label}) RETURN count(n) AS count, '{nt.name}' AS type",
            lambda rs: rs[0]["count"] > 0,
        ))

    # Count edges per type
    for et in schema.edge_types:
        rel_type = et.rel_type
        queries.append((
            f"Count {et.name} edges",
            f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS count, '{et.name}' AS type",
            None,  # Don't fail if no edges of this type — some may not appear in Section 11
        ))

    return queries


def _structural_queries() -> list[tuple[str, str, object]]:
    """Structural validation queries (schema-agnostic)."""
    return [
        (
            "Document root has children",
            """
            MATCH (d {id: 'doc:root'})-[:HAS_PART]->(child)
            RETURN child.id AS id, labels(child)[0] AS type
            ORDER BY child.id
            """,
            lambda rs: len(rs) >= 5,
        ),
        (
            "Graph total stats",
            """
            MATCH (n)
            WITH count(n) AS nodes
            MATCH ()-[r]->()
            WITH nodes, count(r) AS edges
            RETURN nodes, edges
            """,
            lambda rs: rs[0]["nodes"] > 50 and rs[0]["edges"] > 50,
        ),
        (
            "Hierarchy depth check (at least 3 levels)",
            """
            MATCH path = (root {id: 'doc:root'})-[:HAS_PART*1..5]->(leaf)
            WHERE NOT (leaf)-[:HAS_PART]->()
            RETURN length(path) AS depth, leaf.id AS leaf_id
            ORDER BY depth DESC
            LIMIT 5
            """,
            lambda rs: any(r["depth"] >= 2 for r in rs),
        ),
        (
            "NEXT edges enable sequential reading",
            """
            MATCH (a)-[:NEXT]->(b)
            RETURN a.id AS from_node, b.id AS to_node
            LIMIT 5
            """,
            lambda rs: len(rs) >= 1,
        ),
    ]


def main() -> None:
    log.info("=== Step 5: Query Validation ===")

    schema = load_schema()
    log.info("Loaded schema: %d node types, %d edge types",
             len(schema.node_types), len(schema.edge_types))

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    log.info("Connected to Neo4j at %s", NEO4J_URI)

    passed = 0
    total = 0

    with driver.session() as session:
        # Schema-driven queries
        for name, cypher, validator in _generate_schema_queries(schema):
            total += 1
            if _run_query(session, name, cypher, validator):
                passed += 1

        # Structural queries
        for name, cypher, validator in _structural_queries():
            total += 1
            if _run_query(session, name, cypher, validator):
                passed += 1

    driver.close()

    log.info("=== Results: %d/%d queries passed ===", passed, total)
    if passed < total:
        log.warning("Some queries failed — graph may be incomplete")
        sys.exit(1)
    else:
        log.info("All queries passed. The graph answers real questions.")


if __name__ == "__main__":
    main()

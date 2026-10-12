"""Integration tests: can domain questions be answered from the graph?

These tests query the Neo4j graph and validate that the extracted
knowledge graph can answer real FRS 102 questions. They require:
  - Neo4j running with a populated graph (docker compose up + 04_build)

The graph now uses SchemaSpec-driven labels (e.g., StructuralElement
instead of Section/Paragraph). Tests query by id prefix and properties.

Skip with: pytest -m "not integration"
"""

from __future__ import annotations

import os

import pytest

neo4j = pytest.importorskip("neo4j")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def driver():
    """Connect to Neo4j, skip if unavailable."""
    drv = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        drv.verify_connectivity()
    except Exception:
        pytest.skip("Neo4j not available")
    yield drv
    drv.close()


@pytest.fixture(scope="module")
def session(driver):
    with driver.session() as s:
        result = s.run("MATCH (n) RETURN count(n) AS c")
        count = result.single()["c"]
        if count < 10:
            pytest.skip("Graph not populated — run 04_build first")
        yield s


# ------------------------------------------------------------------
# Ground truth Q&A for FRS 102 Section 11
# ------------------------------------------------------------------


class TestSection11Structure:
    """Verify structural completeness of Section 11."""

    def test_section_11_exists(self, session):
        result = session.run(
            "MATCH (s {id: 's:11'}) RETURN s.title AS title"
        )
        record = result.single()
        assert record is not None
        assert "Financial Instruments" in record["title"]

    def test_section_11_has_elements(self, session):
        result = session.run(
            "MATCH (s {id: 's:11'})-[:HAS_PART]->(el) "
            "RETURN count(el) AS c"
        )
        count = result.single()["c"]
        assert count >= 30, f"Expected 30+ child elements, got {count}"

    def test_document_root_exists(self, session):
        result = session.run("MATCH (d {id: 'doc:root'}) RETURN count(d) AS c")
        assert result.single()["c"] == 1


class TestSection11Content:
    """Verify extracted content quality."""

    def test_structural_elements_have_text(self, session):
        """StructuralElements should have text_content."""
        result = session.run(
            "MATCH (el:StructuralElement) "
            "WHERE el.text_content IS NOT NULL AND el.text_content <> '' "
            "RETURN count(el) AS c"
        )
        count = result.single()["c"]
        assert count >= 20, f"Expected 20+ elements with text, got {count}"

    def test_defined_terms_exist(self, session):
        """Defined terms should be extracted."""
        result = session.run(
            "MATCH (t:DefinedTerm) RETURN count(t) AS c"
        )
        count = result.single()["c"]
        assert count >= 5, f"Expected 5+ defined terms, got {count}"


class TestSection11Relationships:
    """Verify relationships are captured."""

    def test_has_references(self, session):
        result = session.run(
            "MATCH ()-[r:REFERENCES]->() RETURN count(r) AS c"
        )
        count = result.single()["c"]
        assert count >= 5, f"Expected 5+ REFERENCES edges, got {count}"

    def test_has_uses_term(self, session):
        result = session.run(
            "MATCH ()-[r:USES_TERM]->() RETURN count(r) AS c"
        )
        count = result.single()["c"]
        assert count >= 5, f"Expected 5+ USES_TERM edges, got {count}"

    def test_hierarchy_depth(self, session):
        """Graph should have at least 3 levels of hierarchy."""
        result = session.run(
            "MATCH path = ({id: 'doc:root'})-[:HAS_PART*1..5]->(leaf) "
            "WHERE NOT (leaf)-[:HAS_PART]->() "
            "RETURN max(length(path)) AS max_depth"
        )
        record = result.single()
        assert record is not None
        assert record["max_depth"] >= 2, "Expected hierarchy depth >= 2"


class TestGraphIntegrity:
    """Verify graph structural integrity."""

    def test_no_self_references(self, session):
        result = session.run(
            "MATCH (n)-[r:REFERENCES]->(n) RETURN count(r) AS c"
        )
        assert result.single()["c"] == 0, "Found self-referencing nodes"

    def test_all_nodes_have_ids(self, session):
        result = session.run(
            "MATCH (n) WHERE n.id IS NULL RETURN count(n) AS c"
        )
        assert result.single()["c"] == 0, "Found nodes without ids"

    def test_next_edges_exist(self, session):
        result = session.run(
            "MATCH ()-[r:NEXT]->() RETURN count(r) AS c"
        )
        count = result.single()["c"]
        assert count >= 5, f"Expected 5+ NEXT edges, got {count}"

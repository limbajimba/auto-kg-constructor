"""Tests for core KG schema models."""

from auto_kg.core.schema import (
    BiTemporalMeta,
    CorpusProfile,
    CrossRefPattern,
    EdgeType,
    FormattingSemantic,
    KGEdge,
    KGNode,
    NodeType,
    NumberingScheme,
)


def test_kg_node_creation():
    node = KGNode(
        id="frs102:v2022:s12.3",
        node_type=NodeType.SUBSECTION,
        label="Section 12.3 - Basic Financial Instruments",
        content="An entity shall recognise a financial asset or liability...",
        level=3,
        numbering="12.3",
    )
    assert node.id == "frs102:v2022:s12.3"
    assert node.node_type == NodeType.SUBSECTION
    assert node.temporal.valid_until is None  # Currently valid


def test_kg_edge_creation():
    edge = KGEdge(
        source_id="frs102:v2022:s12",
        target_id="frs102:v2022:s12.3",
        edge_type=EdgeType.CONTAINS,
    )
    assert edge.edge_type == EdgeType.CONTAINS
    assert edge.weight == 1.0


def test_corpus_profile():
    profile = CorpusProfile(
        corpus_name="FRS 102",
        document_type="accounting_standard",
        hierarchy_levels=["part", "section", "subsection", "paragraph"],
        numbering_schemes=[
            NumberingScheme(
                pattern=r"\d+\.\d+[A-Z]?",
                example="12.3A",
                description="Decimal with optional letter suffix",
            )
        ],
        crossref_patterns=[
            CrossRefPattern(
                pattern=r"(?:see |refer to )(?:paragraph |section )([\d.]+[A-Z]?)",
                example="see paragraph 12.3",
                ref_type="internal",
            )
        ],
        formatting_semantics=[
            FormattingSemantic(
                formatting="bold",
                semantic="mandatory_requirement",
                confidence=0.95,
            )
        ],
    )
    assert profile.document_type == "accounting_standard"
    assert len(profile.numbering_schemes) == 1
    assert profile.formatting_semantics[0].confidence == 0.95


def test_bitemporal_meta_defaults():
    meta = BiTemporalMeta()
    assert meta.valid_from is None
    assert meta.valid_until is None
    assert meta.recorded_at is not None

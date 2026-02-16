"""Knowledge Graph schema — structure-preserving, bi-temporal.

The core insight: nodes ARE structural elements (sections, paragraphs, defined terms,
tables, figures). Edges ARE structural relationships (parent-child, cross-reference,
definition-usage, amendment-chain). This is fundamentally different from entity-extraction
KGs where nodes are real-world entities mentioned in text.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Node Types ---


class NodeType(str, Enum):
    """Types of structural elements that become KG nodes."""

    CORPUS = "corpus"  # The corpus itself (e.g., "UK GAAP Standards")
    DOCUMENT = "document"  # A specific document (e.g., "FRS 102")
    VERSION = "version"  # A specific version/edition of a document
    PART = "part"  # Major division (Part, Chapter, Book)
    SECTION = "section"  # Numbered section (e.g., "Section 12")
    SUBSECTION = "subsection"  # Sub-numbered section (e.g., "12.3")
    PARAGRAPH = "paragraph"  # Individual paragraph (e.g., "12.3A")
    TABLE = "table"  # Table element
    FIGURE = "figure"  # Figure/diagram
    APPENDIX = "appendix"  # Appendix
    GLOSSARY = "glossary"  # Glossary/definitions section
    DEFINED_TERM = "defined_term"  # A defined term (e.g., "financial instrument")
    FOOTNOTE = "footnote"  # Footnote
    EXAMPLE = "example"  # Example block
    AMENDMENT = "amendment"  # An amendment event


# --- Edge Types ---


class EdgeType(str, Enum):
    """Types of structural relationships between nodes."""

    # Hierarchy
    CONTAINS = "contains"  # Parent-child in document structure
    FOLLOWS = "follows"  # Sequential ordering (sibling relationship)

    # Cross-references
    REFERENCES = "references"  # Explicit cross-reference ("see paragraph 12.3")
    REFERENCES_EXTERNAL = "references_external"  # Cross-corpus reference

    # Definitions
    DEFINES = "defines"  # Glossary entry → defined term
    USES_TERM = "uses_term"  # Paragraph → defined term it uses

    # Temporal / amendments
    AMENDS = "amends"  # Amendment → affected node
    SUPERSEDES = "supersedes"  # New version → old version
    EFFECTIVE_FROM = "effective_from"  # Amendment → effective date event

    # Semantic
    REQUIRES = "requires"  # Mandatory requirement relationship
    PERMITS = "permits"  # Permissive/optional relationship
    CONSTRAINS = "constrains"  # External constraint (e.g., Companies Act → FRS 102)


# --- Temporal Metadata ---


class BiTemporalMeta(BaseModel):
    """Bi-temporal tracking for every node and edge.

    - valid_from/valid_until: when this fact is true in the real world
    - recorded_at: when we recorded this in the KG
    """

    valid_from: datetime | None = None
    valid_until: datetime | None = None  # None = currently valid
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- Node & Edge Models ---


class KGNode(BaseModel):
    """A node in the knowledge graph = a structural element from the corpus."""

    id: str  # Deterministic ID: e.g., "frs102:v2022:s12.3"
    node_type: NodeType
    label: str  # Human-readable label (e.g., "Section 12.3 - Basic Financial Instruments")
    content: str | None = None  # Verbatim text content (for leaf nodes)
    content_hash: str | None = None  # SHA256 of content for change detection
    level: int = 0  # Depth in hierarchy (0 = corpus, 1 = document, ...)
    numbering: str | None = None  # Original numbering (e.g., "12.3A")
    formatting: dict[str, Any] = Field(default_factory=dict)  # Preserved formatting semantics
    metadata: dict[str, Any] = Field(default_factory=dict)  # Extensible metadata
    temporal: BiTemporalMeta = Field(default_factory=BiTemporalMeta)


class KGEdge(BaseModel):
    """An edge in the knowledge graph = a structural relationship."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    label: str | None = None  # Optional description (e.g., "see paragraph 12.3")
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    temporal: BiTemporalMeta = Field(default_factory=BiTemporalMeta)


# --- Corpus Profile (output of corpus-profiler agent) ---


class NumberingScheme(BaseModel):
    """A discovered numbering pattern in the corpus."""

    pattern: str  # Regex pattern
    example: str  # Example match
    description: str  # Human-readable description


class CrossRefPattern(BaseModel):
    """A discovered cross-reference pattern."""

    pattern: str  # Regex pattern
    example: str
    ref_type: str  # "internal", "external", "ambiguous"


class FormattingSemantic(BaseModel):
    """A discovered formatting → meaning mapping."""

    formatting: str  # e.g., "bold"
    semantic: str  # e.g., "mandatory_requirement"
    confidence: float  # 0-1


class CorpusProfile(BaseModel):
    """Output of the corpus-profiler agent — a complete profile of corpus patterns."""

    corpus_name: str
    document_type: str  # e.g., "accounting_standard", "legislation", "medical_textbook"
    hierarchy_levels: list[str]  # e.g., ["part", "section", "subsection", "paragraph"]
    numbering_schemes: list[NumberingScheme]
    crossref_patterns: list[CrossRefPattern]
    formatting_semantics: list[FormattingSemantic]
    glossary_convention: str | None = None  # How defined terms are presented
    amendment_convention: str | None = None  # How amendments are structured
    metadata: dict[str, Any] = Field(default_factory=dict)

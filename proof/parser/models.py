"""Extraction schemas for Gemini structured output.

Phase 1 (outline) uses Pydantic models for Gemini's response_schema —
outlines are universal across any document (hierarchy, page ranges).

Phase 2 (section detail) is schema-less — the LLM returns free-form JSON
driven by the SchemaSpec discovered from the document profile. No hardcoded
extraction models.

IMPORTANT: Gemini's response_schema does NOT support Pydantic default
values. Every field must be either required or Optional[T].
Do NOT use Field(default=...) or Field(default_factory=...).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------
# Phase 1: Document Outline extraction (structured — universal)
# -----------------------------------------------------------------------


class OutlineEntry(BaseModel):
    """A single entry in the document's hierarchical outline."""

    number: str = Field(
        description=(
            "The section/paragraph number as it appears in the document "
            "(e.g., '11', '11.2', '11.2A')"
        ),
    )
    title: str = Field(
        description="The title or heading text of this section/paragraph",
    )
    level: int = Field(
        description=(
            "Hierarchy depth: 0=document, 1=part, 2=section, "
            "3=subsection, 4=paragraph, 5=subparagraph"
        ),
    )
    page_start: int = Field(
        description="First page where this section appears (1-indexed)",
    )
    page_end: int = Field(
        description="Last page where this section appears (1-indexed)",
    )
    parent_number: Optional[str] = Field(
        description="The number of the parent section, or null if top-level",
    )
    element_type: str = Field(
        description=(
            "The structural element type as it appears in the document "
            "(e.g., 'section', 'paragraph', 'appendix', 'chapter', 'article'). "
            "Use the document's own terminology."
        ),
    )


class DocumentMetadata(BaseModel):
    """Top-level metadata about the document."""

    title: str = Field(description="Full document title")
    subtitle: Optional[str] = Field(description="Subtitle if present")
    version: Optional[str] = Field(
        description=(
            "Version or edition identifier "
            "(e.g., 'January 2024', 'Third Edition')"
        ),
    )
    effective_date: Optional[str] = Field(
        description="Effective date in ISO 8601 format if stated (e.g., '2024-01-01')",
    )
    issuing_body: Optional[str] = Field(
        description=(
            "Organization that issued the document "
            "(e.g., 'Financial Reporting Council')"
        ),
    )
    total_pages: int = Field(description="Total number of pages in the document")
    document_type: Optional[str] = Field(
        description=(
            "Type of document: standard, regulation, legislation, "
            "guideline, textbook, manual, other"
        ),
    )


class DocumentOutline(BaseModel):
    """Phase 1 output: the complete document structure."""

    metadata: DocumentMetadata
    entries: list[OutlineEntry] = Field(
        description=(
            "All structural entries in document order, "
            "forming a complete table of contents"
        ),
    )

"""Parser protocol — the contract any document parser must fulfil.

Uses typing.Protocol (structural subtyping) so any class with the
right methods works. No inheritance required.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from pathlib import Path

from proof.parser.models import DocumentOutline


@dataclass
class ParseResult:
    """The complete result of parsing a document."""

    # Phase 1 output (structured — universal)
    outline: DocumentOutline

    # Phase 2 output (schema-less — driven by SchemaSpec)
    section_details: list[dict] = field(default_factory=list)

    # Metadata
    input_path: str = ""
    input_sha256: str = ""
    parser_name: str = ""
    model_name: str = ""
    phase1_seconds: float = 0.0
    phase2_seconds: float = 0.0


class ParserProtocol(typing.Protocol):
    """Protocol that any document parser must implement."""

    @property
    def name(self) -> str:
        """Human-readable parser name (e.g., 'gemini:gemini-2.5-pro')."""
        ...

    def extract_outline(self, pdf_path: Path) -> DocumentOutline:
        """Phase 1: Extract the full document structure/outline."""
        ...

    def extract_section_detail(
        self,
        pdf_path: Path,
        section_id: str,
        page_start: int,
        page_end: int,
    ) -> dict:
        """Phase 2: Extract detailed content for a specific section (schema-less)."""
        ...

    def parse(
        self,
        pdf_path: Path,
        target_sections: list[str] | None = None,
    ) -> ParseResult:
        """Full parse: Phase 1 (outline) + Phase 2 (details for targets)."""
        ...

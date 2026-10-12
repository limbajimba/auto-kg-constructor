"""PDF utilities for chunked extraction and text hydration.

Two concerns:
1. Page-range extraction — slice PDF so the LLM only sees relevant pages
2. Text hydration — extract text from PDF pages and attach to LLM-discovered
   structural elements. This implements the agent-tool pattern: the LLM
   discovers structure, this tool does the mechanical text extraction.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from proof.log import get_logger

log = get_logger("proof.parser.pdf_utils")


def pdf_metadata(pdf_path: Path) -> dict:
    """Get basic PDF metadata without reading full content."""
    reader = PdfReader(pdf_path)
    return {
        "pages": len(reader.pages),
        "size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 2),
        "has_toc": len(reader.outline) > 0 if reader.outline else False,
    }


def extract_page_range(
    pdf_path: Path,
    page_start: int,
    page_end: int,
    output_dir: Path | None = None,
) -> Path:
    """Extract a page range into a temporary PDF.

    Args:
        pdf_path: Source PDF
        page_start: First page (1-indexed, inclusive)
        page_end: Last page (1-indexed, inclusive)
        output_dir: Where to write the temp file (default: system temp)

    Returns:
        Path to the extracted PDF (caller should clean up when done)
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    # Convert 1-indexed to 0-indexed
    start_idx = max(0, page_start - 1)
    end_idx = min(len(reader.pages), page_end)

    for i in range(start_idx, end_idx):
        writer.add_page(reader.pages[i])

    # Write to temp file
    suffix = f"_p{page_start}-{page_end}.pdf"
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix=suffix)
    else:
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)

    import os
    os.close(fd)

    out = Path(tmp_path)
    with open(out, "wb") as f:
        writer.write(f)

    page_count = end_idx - start_idx
    log.info(
        "Extracted pages %d-%d (%d pages, %.1f KB) → %s",
        page_start, page_end, page_count,
        out.stat().st_size / 1024, out.name,
    )
    return out


# ---------------------------------------------------------------------------
# Text extraction (tool for text hydration)
# ---------------------------------------------------------------------------


def extract_page_text(pdf_path: Path, page_number: int) -> str:
    """Extract text from a single page (1-indexed)."""
    reader = PdfReader(pdf_path)
    idx = page_number - 1
    if idx < 0 or idx >= len(reader.pages):
        return ""
    return reader.pages[idx].extract_text() or ""


def assess_text_quality(text: str) -> tuple[bool, str]:
    """Assess whether pypdf extracted usable text from a page.

    Returns (is_good, reason). Used to decide if LLM fallback is needed.
    """
    if not text or len(text.strip()) < 50:
        return False, "too_short"
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if len(text) > 0 and non_ascii / len(text) > 0.3:
        return False, "high_non_ascii"
    return True, "ok"


# ---------------------------------------------------------------------------
# TextHydrator — deterministic page-text tool
# ---------------------------------------------------------------------------


class TextHydrator:
    """Deterministic tool: attaches PDF page text to LLM-discovered nodes.

    The LLM already reads the PDF — that's where the cost is. While reading,
    it outputs rich metadata per node (page_start, page_end, identifier,
    semantic_role, etc.). These properties ARE the knowledge graph.

    This tool does one simple thing: given the node's page_start, extract
    the page text from the PDF and attach it. No regex. No matching.
    Just page number → page text. Dead simple, never fails.

    For targeted reading later (e.g. verification), an agent uses the
    node's metadata to know exactly which page to re-read — not the
    whole section.
    """

    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path
        self._reader = PdfReader(pdf_path)
        self._page_cache: dict[int, str] = {}
        self._total_pages = len(self._reader.pages)

    def _get_page_text(self, page_number: int) -> str:
        """Extract text from a PDF page (1-indexed). Cached."""
        if page_number not in self._page_cache:
            idx = page_number - 1
            if 0 <= idx < self._total_pages:
                self._page_cache[page_number] = (
                    self._reader.pages[idx].extract_text() or ""
                )
            else:
                self._page_cache[page_number] = ""
        return self._page_cache[page_number]

    def hydrate(
        self,
        section_detail: dict,
        section_page_start: int,
        section_page_end: int,
    ) -> dict:
        """Attach page text to all elements in a section.

        Uses each element's page_start metadata (set by the LLM) to pull
        the right page text. Auto-detects if the LLM used the document's
        printed page numbers vs PDF page indices.
        """
        elements = section_detail.get("elements", [])
        if not elements:
            return section_detail

        # Detect offset between LLM page numbers and PDF page indices
        page_offset = self._detect_page_offset(
            elements, section_page_start, section_page_end
        )

        # Assess quality across section pages
        poor_pages: list[int] = []
        for pg in range(section_page_start, section_page_end + 1):
            text = self._get_page_text(pg)
            good, reason = assess_text_quality(text)
            if not good:
                poor_pages.append(pg)
                log.warning("Poor pypdf quality on page %d: %s", pg, reason)

        for el in elements:
            props = el.setdefault("properties", {})

            # Resolve PDF page from LLM's page_start
            pg_start = self._resolve_page(
                props.get("page_start"), page_offset, section_page_start
            )
            pg_end = self._resolve_page(
                props.get("page_end"), page_offset, pg_start
            )

            # Simple: extract text from the element's page(s)
            if pg_start == pg_end:
                text = self._get_page_text(pg_start)
            else:
                text = "\n".join(
                    self._get_page_text(pg)
                    for pg in range(pg_start, pg_end + 1)
                )

            props["text_content"] = text
            props["text_source"] = "pypdf"
            props["pdf_page"] = pg_start

        section_id = section_detail.get("section_id", "?")
        log.info(
            "Hydrated section %s: %d elements, page_offset=%+d, %d poor pages",
            section_id, len(elements), page_offset, len(poor_pages),
        )

        section_detail["hydration_stats"] = {
            "hydrated": len(elements),
            "total": len(elements),
            "page_offset": page_offset,
            "poor_pages": poor_pages,
        }
        return section_detail

    def _detect_page_offset(
        self,
        elements: list[dict],
        section_page_start: int,
        section_page_end: int,
    ) -> int:
        """Detect offset between LLM page numbers and PDF page indices.

        FRS 102 example: LLM says page_start=118, but the PDF page is 122.
        The printed page says "118" but it's the 122nd page in the PDF.
        Offset = +4.
        """
        llm_pages = []
        for el in elements:
            raw = el.get("properties", {}).get("page_start")
            if raw is not None:
                try:
                    llm_pages.append(int(raw))
                except (TypeError, ValueError):
                    pass

        if not llm_pages:
            return 0

        min_llm = min(llm_pages)

        # If LLM pages are already in the PDF range, no offset needed
        if section_page_start <= min_llm <= section_page_end:
            return 0

        # Align LLM's first page to the section's PDF start
        offset = section_page_start - min_llm
        log.info(
            "Page offset detected: LLM min=%d, PDF section start=%d, offset=%+d",
            min_llm, section_page_start, offset,
        )
        return offset

    def _resolve_page(
        self,
        raw_page: int | str | None,
        offset: int,
        fallback: int,
    ) -> int:
        """Convert LLM page number → PDF page index."""
        if raw_page is None:
            return fallback
        try:
            pg = int(raw_page) + offset
        except (TypeError, ValueError):
            return fallback
        return max(1, min(pg, self._total_pages))

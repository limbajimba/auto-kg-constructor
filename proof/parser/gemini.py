"""Gemini 2.5 Pro parser implementation.

Phase 1 (outline): Uses Pydantic response_schema — outlines are universal.
Phase 2 (section detail): Schema-less JSON — driven by SchemaSpec from profile.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from proof.config import (
    GEMINI_API_KEY,
    GEMINI_MAX_RETRIES,
    GEMINI_MODEL,
    GEMINI_RETRY_BASE_SECONDS,
    MAX_PAGES_PER_CHUNK,
    PARSE_CACHE_DIR,
    PARSE_TIMEOUT_SECONDS,
)
from proof.log import get_logger
from proof.parser.cache import ParseCache
from proof.parser.models import DocumentOutline
from proof.parser.prompts import build_phase1_prompt, build_phase2_prompt
from proof.parser.protocol import ParseResult

if TYPE_CHECKING:
    from proof.parser.manifest import ExtractionManifest
    from proof.schema import SchemaSpec

log = get_logger("proof.parser.gemini")


class GeminiParser:
    """Parses documents using Gemini 2.5 Pro's native PDF vision."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        profile: dict | None = None,
        schema: "SchemaSpec | None" = None,
    ) -> None:
        self._api_key = api_key or GEMINI_API_KEY
        self._model = model or GEMINI_MODEL
        self._profile = profile
        self._schema = schema
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY must be set in environment or passed explicitly. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        self._client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=PARSE_TIMEOUT_SECONDS * 1000),
        )
        self._cache = ParseCache(PARSE_CACHE_DIR)
        self._uploaded_files: dict[str, types.File] = {}
        log.info("GeminiParser initialised (model=%s)", self._model)

    @property
    def name(self) -> str:
        return f"gemini:{self._model}"

    # ------------------------------------------------------------------
    # File upload
    # ------------------------------------------------------------------

    def _upload_pdf(self, pdf_path: Path) -> types.File:
        """Upload PDF to Gemini Files API (deduplicates within session)."""
        key = str(pdf_path.resolve())
        if key in self._uploaded_files:
            log.info("Reusing previously uploaded file for %s", pdf_path.name)
            return self._uploaded_files[key]
        log.info("Uploading %s to Gemini Files API...", pdf_path.name)
        t0 = time.monotonic()
        uploaded = self._client.files.upload(file=pdf_path)
        elapsed = time.monotonic() - t0
        log.info("Upload complete in %.1fs (name=%s)", elapsed, uploaded.name)
        self._uploaded_files[key] = uploaded
        return uploaded

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    def _generate_with_retry(
        self,
        contents: list,
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        """Call generate_content with exponential backoff retry."""
        last_error: Exception | None = None
        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                return response
            except Exception as exc:
                last_error = exc
                if attempt < GEMINI_MAX_RETRIES:
                    wait = GEMINI_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    log.warning(
                        "Gemini API error (attempt %d/%d): %s — retrying in %.1fs",
                        attempt,
                        GEMINI_MAX_RETRIES,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    log.error(
                        "Gemini API failed after %d attempts: %s",
                        GEMINI_MAX_RETRIES,
                        exc,
                    )
        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Phase 1: Document outline (structured — universal)
    # ------------------------------------------------------------------

    def extract_outline(self, pdf_path: Path) -> DocumentOutline:
        """Extract the full document structure/outline."""
        cache_key = f"outline:{self._cache.file_hash(pdf_path)}"
        cached = self._cache.load(cache_key, DocumentOutline)
        if cached is not None:
            return cached

        uploaded_file = self._upload_pdf(pdf_path)

        prompt = build_phase1_prompt(self._profile)
        log.info("Phase 1: Extracting document outline...")
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DocumentOutline,
            temperature=0.0,
        )

        t0 = time.monotonic()
        response = self._generate_with_retry(
            contents=[uploaded_file, prompt],
            config=config,
        )
        elapsed = time.monotonic() - t0

        outline = DocumentOutline.model_validate_json(response.text)
        log.info(
            "Phase 1 complete in %.1fs: %d entries, %d pages",
            elapsed,
            len(outline.entries),
            outline.metadata.total_pages,
        )

        self._cache.save(cache_key, outline)
        return outline

    # ------------------------------------------------------------------
    # Phase 2: Section detail (schema-less — driven by SchemaSpec)
    # ------------------------------------------------------------------

    def _extract_chunk(
        self,
        pdf_path: Path,
        section_id: str,
        page_start: int,
        page_end: int,
        manifest: "ExtractionManifest | None" = None,
    ) -> dict:
        """Extract a single page-range chunk. Returns raw dict.

        This is the low-level method that talks to Gemini. It does NOT
        handle truncation — the caller is responsible for splitting.
        """
        from proof.parser.pdf_utils import extract_page_range

        chunk_pdf = extract_page_range(pdf_path, page_start, page_end)
        try:
            uploaded_file = self._upload_pdf(chunk_pdf)

            prompt = build_phase2_prompt(
                section_number=section_id,
                page_start=page_start,
                page_end=page_end,
                profile=self._profile,
                schema=self._schema,
                manifest=manifest,
            )

            log.info(
                "Phase 2: Extracting section %s (pages %d–%d)...",
                section_id,
                page_start,
                page_end,
            )

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            )

            t0 = time.monotonic()
            response = self._generate_with_retry(
                contents=[uploaded_file, prompt],
                config=config,
            )
            elapsed = time.monotonic() - t0

            # Detect truncation via finish_reason or JSON parse failure
            truncated = False
            candidate = response.candidates[0] if response.candidates else None
            if candidate and candidate.finish_reason and candidate.finish_reason.name == "MAX_TOKENS":
                truncated = True

            try:
                detail = json.loads(response.text)
            except json.JSONDecodeError:
                truncated = True
                detail = None

            if truncated:
                log.warning(
                    "Response truncated for section %s pages %d–%d (%d chars). "
                    "Will sub-chunk.",
                    section_id, page_start, page_end,
                    len(response.text) if response.text else 0,
                )
                raise _TruncatedResponse(section_id, page_start, page_end)

            elements = detail.get("elements", [])
            type_counts: dict[str, int] = {}
            for el in elements:
                t = el.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1

            log.info(
                "Phase 2 section %s pages %d–%d complete in %.1fs: %d elements (%s)",
                section_id, page_start, page_end, elapsed,
                len(elements),
                ", ".join(f"{k}:{v}" for k, v in sorted(type_counts.items())),
            )

            return detail
        finally:
            chunk_pdf.unlink(missing_ok=True)
            key = str(chunk_pdf.resolve())
            self._uploaded_files.pop(key, None)

    def extract_section_detail(
        self,
        pdf_path: Path,
        section_id: str,
        page_start: int,
        page_end: int,
        manifest: "ExtractionManifest | None" = None,
    ) -> dict:
        """Extract detailed content for a section, auto-sub-chunking if needed.

        If the section spans more pages than MAX_PAGES_PER_CHUNK, it is
        split into sub-chunks upfront. If the LLM response is truncated
        (hit output token limit), the chunk is split in half and retried.

        Returns merged dict with all elements.
        """
        file_hash = self._cache.file_hash(pdf_path)
        manifest_key = len(manifest.nodes) if manifest else 0
        cache_key = f"section_v5:{file_hash}:{section_id}:p{page_start}-{page_end}:m{manifest_key}"
        cached = self._cache.load_raw(cache_key)
        if cached is not None:
            return cached

        num_pages = page_end - page_start + 1

        # Split into sub-chunks if too large
        if num_pages > MAX_PAGES_PER_CHUNK:
            log.info(
                "Section %s spans %d pages — splitting into sub-chunks of %d pages",
                section_id, num_pages, MAX_PAGES_PER_CHUNK,
            )
            merged = self._extract_sub_chunks(
                pdf_path, section_id, page_start, page_end, manifest
            )
        else:
            try:
                merged = self._extract_chunk(
                    pdf_path, section_id, page_start, page_end, manifest
                )
            except _TruncatedResponse:
                # Split in half and retry
                merged = self._extract_sub_chunks(
                    pdf_path, section_id, page_start, page_end, manifest
                )

        self._cache.save_raw(cache_key, merged)
        return merged

    def _extract_sub_chunks(
        self,
        pdf_path: Path,
        section_id: str,
        page_start: int,
        page_end: int,
        manifest: "ExtractionManifest | None" = None,
    ) -> dict:
        """Split a page range into sub-chunks and merge results."""
        from proof.parser.manifest import ExtractionManifest

        # Build sub-chunk ranges
        ranges: list[tuple[int, int]] = []
        p = page_start
        while p <= page_end:
            chunk_end = min(p + MAX_PAGES_PER_CHUNK - 1, page_end)
            ranges.append((p, chunk_end))
            p = chunk_end + 1

        log.info(
            "Sub-chunking section %s into %d chunks: %s",
            section_id, len(ranges),
            [(s, e) for s, e in ranges],
        )

        # Use a local manifest copy so sub-chunks see each other's nodes
        local_manifest = ExtractionManifest.from_dict(
            manifest.to_dict() if manifest else {"nodes": {}, "extracted_sections": []}
        )

        all_elements: list[dict] = []
        for chunk_start, chunk_end in ranges:
            try:
                detail = self._extract_chunk(
                    pdf_path, section_id, chunk_start, chunk_end, local_manifest
                )
            except _TruncatedResponse:
                # If still truncated, split this sub-chunk further (recursive)
                if chunk_end - chunk_start >= 2:
                    mid = (chunk_start + chunk_end) // 2
                    log.warning(
                        "Sub-chunk %d–%d still truncated, splitting at page %d",
                        chunk_start, chunk_end, mid,
                    )
                    detail = self._extract_sub_chunks(
                        pdf_path, section_id, chunk_start, mid, local_manifest
                    )
                    detail2 = self._extract_sub_chunks(
                        pdf_path, section_id, mid + 1, chunk_end, local_manifest
                    )
                    # Merge the two halves
                    detail["elements"].extend(detail2.get("elements", []))
                else:
                    log.error(
                        "Cannot sub-chunk further: pages %d–%d",
                        chunk_start, chunk_end,
                    )
                    detail = {"section_id": section_id, "elements": []}

            # Update local manifest with newly extracted elements
            for el in detail.get("elements", []):
                el_id = el.get("id", "")
                el_type = el.get("type", "unknown")
                if el_id:
                    local_manifest.add_node(el_id, node_type=el_type, section=section_id)

            all_elements.extend(detail.get("elements", []))

        return {"section_id": section_id, "elements": all_elements}

    # ------------------------------------------------------------------
    # Full parse
    # ------------------------------------------------------------------

    def parse(
        self,
        pdf_path: Path,
        target_sections: list[str] | None = None,
    ) -> ParseResult:
        """Full parse: Phase 1 + Phase 2 for target sections.

        Builds a manifest incrementally so each section knows what
        nodes already exist from previous sections.
        """
        from proof.parser.manifest import ExtractionManifest

        log.info("=== Starting parse of %s ===", pdf_path.name)

        # Phase 1: outline
        t0 = time.monotonic()
        outline = self.extract_outline(pdf_path)
        phase1_seconds = time.monotonic() - t0

        # Build initial manifest from outline (all sections are known)
        manifest = ExtractionManifest()
        manifest.add_from_outline(
            [e.model_dump() for e in outline.entries]
        )
        log.info("Manifest initialized: %d outline nodes", len(manifest.nodes))

        # Determine which sections to extract in detail
        if target_sections is None:
            sections_to_extract = [
                e for e in outline.entries if e.element_type == "section"
            ]
        else:
            sections_to_extract = [
                e for e in outline.entries if e.number in target_sections
            ]

        if not sections_to_extract:
            log.warning("No sections matched for detail extraction")

        log.info(
            "Extracting %d section(s) in detail: %s",
            len(sections_to_extract),
            [e.number for e in sections_to_extract],
        )

        # Phase 2: section details (chunked, manifest-aware)
        t1 = time.monotonic()
        section_details: list[dict] = []
        for entry in sections_to_extract:
            detail = self.extract_section_detail(
                pdf_path=pdf_path,
                section_id=entry.number,
                page_start=entry.page_start,
                page_end=entry.page_end,
                manifest=manifest,
            )
            section_details.append(detail)

            # Update manifest with newly extracted elements
            manifest.add_from_extraction(
                entry.number,
                detail.get("elements", []),
            )
            log.info(
                "Manifest updated: %d total nodes, %d sections extracted",
                len(manifest.nodes),
                len(manifest.extracted_sections),
            )

        phase2_seconds = time.monotonic() - t1

        # Phase 3: Text hydration — tool extracts text from PDF pages
        from proof.parser.pdf_utils import TextHydrator

        hydrator = TextHydrator(pdf_path)
        section_pages = {e.number: (e.page_start, e.page_end) for e in outline.entries}

        log.info("Hydrating text for %d sections from PDF...", len(section_details))
        for detail in section_details:
            sid = detail.get("section_id", "")
            pg_start, pg_end = section_pages.get(
                sid, (1, outline.metadata.total_pages)
            )
            hydrator.hydrate(detail, pg_start, pg_end)

        result = ParseResult(
            outline=outline,
            section_details=section_details,
            input_path=str(pdf_path),
            input_sha256=self._cache.file_hash(pdf_path),
            parser_name=self.name,
            model_name=self._model,
            phase1_seconds=phase1_seconds,
            phase2_seconds=phase2_seconds,
        )

        log.info(
            "Parse complete: %.1fs total (phase1=%.1fs, phase2=%.1fs, %d sections)",
            phase1_seconds + phase2_seconds,
            phase1_seconds,
            phase2_seconds,
            len(section_details),
        )

        return result


class _TruncatedResponse(Exception):
    """Raised when Gemini's response is truncated (output token limit)."""

    def __init__(self, section_id: str, page_start: int, page_end: int):
        self.section_id = section_id
        self.page_start = page_start
        self.page_end = page_end
        super().__init__(f"Truncated response for {section_id} pages {page_start}-{page_end}")

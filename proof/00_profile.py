"""Step 0: Document self-discovery — profile a PDF before extraction.

Run:  uv run python -m proof.00_profile
      uv run python -m proof.00_profile --pdf path/to/other.pdf

This script uploads a PDF to Gemini and asks open-ended discovery
questions. The LLM explores the document freely and reports what it
finds — structure, patterns, conventions, relationships. No rigid
schema constrains what it discovers.

The output (document_profile.json) drives all downstream steps:
adaptive extraction prompts, dynamic KG schema, quality validation.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from google import genai
from google.genai import types

from proof.config import (
    FRS102_PDF,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_RETRY_BASE_SECONDS,
    GEMINI_MAX_RETRIES,
    MAX_PDF_SIZE_MB,
    OUTPUT_DIR,
    PARSE_CACHE_DIR,
)
from proof.log import get_logger
from proof.parser.cache import ParseCache

log = get_logger("proof.00_profile")

# --------------------------------------------------------------------------
# Discovery prompt — intentionally open-ended
# --------------------------------------------------------------------------

DISCOVERY_PROMPT = """\
You are a document analyst examining a PDF for the first time. You have \
no prior knowledge of this document. Your job is to explore it thoroughly \
and report everything you discover about its structure and patterns.

Examine the ENTIRE document and respond with a JSON object containing \
your discoveries. You decide what keys and structure to use based on \
what you actually find. However, you MUST cover these areas:

1. **identity**: What is this document? Title, author/issuer, date, \
edition, domain, document type. Whatever identifying information exists.

2. **structure**: What structural elements exist? (chapters, sections, \
articles, paragraphs, schedules, appendices, etc.) How deep is the \
hierarchy? What numbering system is used? Describe each level you find \
with examples.

3. **patterns**: What formatting conventions carry semantic meaning? \
(e.g., bold text = requirement, italic = defined term, indentation = \
sub-clause). What recurring patterns do you see?

4. **relationships**: What types of cross-references exist? Internal \
references (between sections), external references (to other documents, \
laws, standards). How are they expressed in text? Give examples.

5. **special_elements**: Tables, figures, examples, definitions, \
glossaries, footnotes, appendices — what special content types exist? \
How are they formatted and referenced?

6. **proposed_kg_schema**: Based on everything you discovered, propose \
node types and edge types for a knowledge graph that would faithfully \
represent this document's structure. For each type, explain what it \
captures and give an example. Include both structural relationships \
(hierarchy, ordering) and semantic relationships (cross-references, \
definitions, amendments).

Be exhaustive and specific. Use concrete examples from the document. \
This profile will drive all downstream processing — anything you miss \
here will be missed everywhere.

Respond with valid JSON only. No markdown, no code fences."""


# --------------------------------------------------------------------------
# Core profiling function
# --------------------------------------------------------------------------


def profile_document(pdf_path: Path) -> dict:
    """Upload PDF to Gemini and run free-form discovery.

    Returns the raw JSON dict from the LLM — no schema imposed.
    """
    cache = ParseCache(PARSE_CACHE_DIR)
    file_hash = cache.file_hash(pdf_path)
    cache_key = f"profile:{file_hash}"

    cached = cache.load_raw(cache_key)
    if cached is not None:
        log.info("Using cached profile")
        return cached

    # Init client
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY must be set. Get one at https://aistudio.google.com/apikey"
        )
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Upload PDF
    log.info("Uploading %s to Gemini Files API...", pdf_path.name)
    t0 = time.monotonic()
    uploaded = client.files.upload(file=pdf_path)
    log.info("Upload complete in %.1fs", time.monotonic() - t0)

    # Run discovery — free-form JSON, no response_schema
    log.info("Running document discovery (model=%s)...", GEMINI_MODEL)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0,
    )

    last_error: Exception | None = None
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            t0 = time.monotonic()
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[uploaded, DISCOVERY_PROMPT],
                config=config,
            )
            elapsed = time.monotonic() - t0
            log.info("Discovery complete in %.1fs", elapsed)
            break
        except Exception as exc:
            last_error = exc
            if attempt < GEMINI_MAX_RETRIES:
                wait = GEMINI_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                log.warning(
                    "Gemini API error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, GEMINI_MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
            else:
                log.error("Gemini API failed after %d attempts", GEMINI_MAX_RETRIES)
                raise last_error  # type: ignore[misc]

    # Parse the free-form JSON
    profile = json.loads(response.text)

    # Cache it
    cache.save_raw(cache_key, profile)
    return profile


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _validate_input(pdf_path: Path) -> None:
    """Validate the input PDF exists and is reasonable."""
    if not pdf_path.exists():
        log.error("PDF not found: %s", pdf_path)
        raise SystemExit(1)
    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_PDF_SIZE_MB:
        log.error("PDF is %.1f MB — exceeds %d MB limit", size_mb, MAX_PDF_SIZE_MB)
        raise SystemExit(1)
    if pdf_path.suffix.lower() != ".pdf":
        log.error("Expected .pdf file, got %s", pdf_path.suffix)
        raise SystemExit(1)
    log.info("Input: %s (%.1f MB)", pdf_path.name, size_mb)


def _print_profile_summary(profile: dict) -> None:
    """Print a human-readable summary of the discovered profile."""
    log.info("--- Document Profile ---")

    # Identity
    identity = profile.get("identity", {})
    if isinstance(identity, dict):
        for key, val in identity.items():
            if isinstance(val, str):
                log.info("  %-20s %s", key, val)

    # Structure summary
    structure = profile.get("structure", {})
    if isinstance(structure, dict):
        log.info("--- Discovered Structure ---")
        levels = structure.get("levels", structure.get("hierarchy", []))
        if isinstance(levels, list):
            for level in levels:
                if isinstance(level, dict):
                    name = level.get("name", level.get("type", "?"))
                    log.info("  %s", name)
                elif isinstance(level, str):
                    log.info("  %s", level)

    # Proposed schema
    schema = profile.get("proposed_kg_schema", {})
    if isinstance(schema, dict):
        log.info("--- Proposed KG Schema ---")
        nodes = schema.get("node_types", [])
        edges = schema.get("edge_types", [])
        if isinstance(nodes, list):
            log.info("  Node types: %d", len(nodes))
            for n in nodes[:10]:
                name = n.get("name", n) if isinstance(n, dict) else n
                log.info("    - %s", name)
        if isinstance(edges, list):
            log.info("  Edge types: %d", len(edges))
            for e in edges[:10]:
                name = e.get("name", e) if isinstance(e, dict) else e
                log.info("    - %s", name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile a PDF document")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=FRS102_PDF,
        help="Path to PDF file",
    )
    args = parser.parse_args()

    log.info("=== Step 0: Document Self-Discovery ===")
    _validate_input(args.pdf)

    profile = profile_document(args.pdf)

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "document_profile.json"
    out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    log.info("Profile saved: %s", out_path)

    _print_profile_summary(profile)

    # Show raw key count for transparency
    log.info("--- Profile Keys: %s ---", list(profile.keys()))
    log.info("Done. Next step: uv run python -m proof.01_parse --sections 11")


if __name__ == "__main__":
    main()

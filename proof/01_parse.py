"""Step 1: Parse a PDF document.

Run:  uv run python -m proof.01_parse
      uv run python -m proof.01_parse --sections 11
      uv run python -m proof.01_parse --pdf path/to/other.pdf

This script:
  1. Validates the input PDF (exists, size, file type)
  2. Loads profile and generates SchemaSpec (from Step 0 + Step 3)
  3. Parses with Gemini 2.5 Pro (Phase 1: outline, Phase 2: schema-driven detail)
  4. Saves structured output as JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from proof.config import FRS102_DOWNLOAD_URL, FRS102_PDF, MAX_PDF_SIZE_MB, OUTPUT_DIR
from proof.log import get_logger
from proof.parser.gemini import GeminiParser
from proof.parser.protocol import ParseResult

PROFILE_PATH = OUTPUT_DIR / "document_profile.json"

log = get_logger("proof.01_parse")


def _sha256(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_input(pdf_path: Path) -> None:
    """Validate the input PDF."""
    if not pdf_path.exists():
        log.error("PDF not found at %s", pdf_path)
        log.error("Download from: %s", FRS102_DOWNLOAD_URL)
        sys.exit(1)

    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_PDF_SIZE_MB:
        log.error("PDF is %.1f MB — exceeds %d MB limit", size_mb, MAX_PDF_SIZE_MB)
        sys.exit(1)

    if pdf_path.suffix.lower() != ".pdf":
        log.error("Expected .pdf file, got %s", pdf_path.suffix)
        sys.exit(1)

    file_hash = _sha256(pdf_path)
    log.info(
        "Input validated: %s (%.1f MB, sha256=%s…)",
        pdf_path.name,
        size_mb,
        file_hash[:12],
    )


def _save_result(result: ParseResult) -> None:
    """Save the ParseResult as JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    result_path = OUTPUT_DIR / "parse_result.json"
    result_data = {
        "metadata": {
            "parser": result.parser_name,
            "model": result.model_name,
            "input_path": result.input_path,
            "input_sha256": result.input_sha256,
            "phase1_seconds": round(result.phase1_seconds, 2),
            "phase2_seconds": round(result.phase2_seconds, 2),
            "timestamp": datetime.now(UTC).isoformat(),
        },
        "outline": result.outline.model_dump(mode="json"),
        "section_details": result.section_details,  # Already raw dicts
    }
    result_path.write_text(json.dumps(result_data, indent=2))
    log.info("Saved parse result: %s", result_path)

    # Summary
    log.info("--- Parse Summary ---")
    log.info("Outline entries: %d", len(result.outline.entries))
    log.info("Sections extracted: %d", len(result.section_details))
    for sd in result.section_details:
        elements = sd.get("elements", [])
        type_counts: dict[str, int] = {}
        for el in elements:
            t = el.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        log.info(
            "  Section %s: %d elements (%s)",
            sd.get("section_id", "?"),
            len(elements),
            ", ".join(f"{k}:{v}" for k, v in sorted(type_counts.items())),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse PDF document")
    parser.add_argument(
        "--sections",
        nargs="*",
        help="Section numbers to extract in detail (default: all)",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=FRS102_PDF,
        help="Path to PDF file",
    )
    args = parser.parse_args()

    log.info("=== Step 1: Parse document with Gemini ===")
    _validate_input(args.pdf)

    # Load profile if available (from Step 0)
    profile = None
    if PROFILE_PATH.exists():
        profile = json.loads(PROFILE_PATH.read_text())
        log.info("Loaded document profile from %s", PROFILE_PATH)
    else:
        log.warning(
            "No document profile found at %s — using generic prompts. "
            "Run Step 0 first: uv run python -m proof.00_profile",
            PROFILE_PATH,
        )

    # Generate schema from profile (Step 3)
    schema = None
    if profile:
        from proof.schema import generate_schema, save_schema

        schema = generate_schema(profile)
        save_schema(schema)
        log.info("Generated SchemaSpec: %d node types, %d edge types",
                 len(schema.node_types), len(schema.edge_types))

    gemini = GeminiParser(profile=profile, schema=schema)
    result = gemini.parse(
        pdf_path=args.pdf,
        target_sections=args.sections,
    )
    _save_result(result)

    log.info("Done. Next step: uv run python -m proof.02_inspect")


if __name__ == "__main__":
    main()

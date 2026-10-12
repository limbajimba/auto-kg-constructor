"""Step 2: Inspect parsed output and validate extraction quality.

Run:  uv run python -m proof.02_inspect
Deps: Step 01 must have completed (outputs/parse_result.json must exist)

Works with both the new schema-less format (elements[]) and reports
element type distribution, relationship patterns, and coverage.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from proof.config import OUTPUT_DIR
from proof.log import get_logger
from proof.parser.models import DocumentOutline

log = get_logger("proof.02_inspect")


def _load_parse_result() -> dict:
    """Load parse_result.json from Step 1."""
    path = OUTPUT_DIR / "parse_result.json"
    if not path.exists():
        log.error("Parse result not found at %s", path)
        log.error("Run Step 1 first: uv run python -m proof.01_parse")
        sys.exit(1)

    log.info("Loading parse result from %s", path)
    return json.loads(path.read_text())


def _inspect_metadata(data: dict) -> None:
    """Inspect parse metadata."""
    log.info("--- Parse Metadata ---")
    meta = data["metadata"]
    for key, val in sorted(meta.items()):
        log.info("  %-20s %s", key, val)


def _inspect_outline(data: dict) -> None:
    """Inspect the document outline."""
    outline = DocumentOutline.model_validate(data["outline"])
    log.info("--- Document: %s ---", outline.metadata.title)
    log.info("  Version:     %s", outline.metadata.version)
    log.info("  Issued by:   %s", outline.metadata.issuing_body)
    log.info("  Total pages: %d", outline.metadata.total_pages)
    log.info("  Entries:     %d", len(outline.entries))

    # Count by element type
    log.info("--- Outline by Element Type ---")
    type_counts: Counter[str] = Counter(e.element_type for e in outline.entries)
    for t, c in type_counts.most_common():
        log.info("  %-25s %d", t, c)

    # Count by hierarchy level
    log.info("--- Outline by Hierarchy Level ---")
    level_counts: Counter[int] = Counter(e.level for e in outline.entries)
    for level in sorted(level_counts):
        log.info("  Level %d: %d entries", level, level_counts[level])

    # Check page coverage
    if outline.entries:
        total_pages = outline.metadata.total_pages
        covered_pages: set[int] = set()
        for e in outline.entries:
            covered_pages.update(range(e.page_start, e.page_end + 1))
        uncovered = set(range(1, total_pages + 1)) - covered_pages
        if uncovered:
            log.warning(
                "  Pages not covered by any entry: %s",
                sorted(uncovered)[:20],
            )
        else:
            log.info("  All %d pages covered by outline entries", total_pages)


def _inspect_section_details(data: dict) -> None:
    """Inspect extracted section details (schema-less elements format)."""
    details = data.get("section_details", [])
    if not details:
        log.info("--- No section details extracted ---")
        return

    log.info("--- Section Details (%d sections) ---", len(details))

    all_elements: list[dict] = []
    all_relationships: list[dict] = []

    for sd in details:
        section_id = sd.get("section_id", "?")
        elements = sd.get("elements", [])
        all_elements.extend(elements)

        # Count by element type
        type_counts: Counter[str] = Counter(
            el.get("type", "unknown") for el in elements
        )
        log.info("  Section %s: %d elements", section_id, len(elements))
        for t, c in type_counts.most_common():
            log.info("    %-25s %d", t, c)

        # Collect relationships
        for el in elements:
            for rel in el.get("relationships", []):
                rel_with_source = {**rel, "_source_id": el.get("id", "?")}
                all_relationships.append(rel_with_source)

    # Overall element type distribution
    log.info("--- All Elements (%d total) ---", len(all_elements))
    overall_types: Counter[str] = Counter(
        el.get("type", "unknown") for el in all_elements
    )
    for t, c in overall_types.most_common():
        log.info("  %-25s %d", t, c)

    # Relationship type distribution
    if all_relationships:
        log.info("--- Relationships (%d total) ---", len(all_relationships))
        rel_types: Counter[str] = Counter(
            r.get("type", "unknown") for r in all_relationships
        )
        for t, c in rel_types.most_common():
            log.info("  %-25s %d", t, c)

        # Show first few examples
        for r in all_relationships[:5]:
            log.info(
                "    [%s] %s → %s",
                r.get("type", "?"),
                r.get("_source_id", "?"),
                r.get("target_id", "?"),
            )

    # Property coverage analysis
    log.info("--- Property Coverage ---")
    for node_type, count in overall_types.most_common():
        type_elements = [el for el in all_elements if el.get("type") == node_type]
        prop_keys: Counter[str] = Counter()
        for el in type_elements:
            for k in el.get("properties", {}).keys():
                prop_keys[k] += 1
        if prop_keys:
            log.info("  %s:", node_type)
            for k, c in prop_keys.most_common():
                pct = c / count * 100
                log.info("    %-20s %d/%d (%.0f%%)", k, c, count, pct)

    # Text hydration quality
    text_sources: Counter[str] = Counter(
        el.get("properties", {}).get("text_source", "none")
        for el in all_elements
    )
    if any(s != "none" for s in text_sources):
        log.info("--- Text Hydration ---")
        for src, cnt in text_sources.most_common():
            log.info("  %-30s %d", src, cnt)

    # Hydration stats from section details
    for sd in details:
        stats = sd.get("hydration_stats")
        if stats:
            log.info(
                "  Section %s: %d hydrated, page_offset=%+d, poor_pages=%s",
                sd.get("section_id", "?"),
                stats.get("hydrated", 0),
                stats.get("page_offset", 0),
                stats.get("poor_pages", []),
            )


def main() -> None:
    log.info("=== Step 2: Inspect Parse Result ===")

    data = _load_parse_result()
    _inspect_metadata(data)
    _inspect_outline(data)
    _inspect_section_details(data)

    log.info("Done. Next step: uv run python -m proof.04_build")


if __name__ == "__main__":
    main()

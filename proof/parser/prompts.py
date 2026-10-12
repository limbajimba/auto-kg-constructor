"""Prompt templates for Gemini document extraction.

Phase 1 prompt is generic (outlines are universal).
Phase 2 prompt is entirely driven by the SchemaSpec discovered from the
document profile — no hardcoded extraction instructions.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from proof.parser.manifest import ExtractionManifest
    from proof.schema import SchemaSpec


def _profile_context(profile: dict | None) -> str:
    """Build a context block from the profile for injection into prompts."""
    if not profile:
        return ""

    parts = ["\n\n--- DOCUMENT PROFILE (discovered during profiling) ---"]

    identity = profile.get("identity", {})
    if identity:
        parts.append(f"Document: {json.dumps(identity)}")

    structure = profile.get("structure", {})
    if structure:
        parts.append(f"Structure: {json.dumps(structure)}")

    patterns = profile.get("patterns", {})
    if patterns:
        parts.append(f"Formatting conventions: {json.dumps(patterns)}")

    relationships = profile.get("relationships", {})
    if relationships:
        parts.append(f"Relationship patterns: {json.dumps(relationships)}")

    special = profile.get("special_elements", [])
    if special:
        parts.append(f"Special elements: {json.dumps(special)}")

    parts.append("--- END PROFILE ---")
    return "\n".join(parts)


def build_phase1_prompt(profile: dict | None = None) -> str:
    """Generate the Phase 1 prompt for document outline extraction.

    If a profile is provided, the prompt references discovered element
    types and hierarchy levels. Otherwise, uses a generic prompt.
    """
    context = _profile_context(profile)

    return f"""\
You are a document structure analyst. Your task is to extract the complete \
hierarchical outline of this PDF document.
{context}

Instructions:
1. Examine every page of the document.
2. Identify ALL structural elements — use the element types discovered in \
the profile above (if provided), or identify them from the document itself.
3. For each element, record:
   - Its number/identifier as printed in the document
   - Its title or heading text
   - Its hierarchy level (0=document root, deeper levels as discovered)
   - The page range where it appears (1-indexed)
   - Its parent element's number (null if top-level)
   - Its element type (using the document's own terminology)
4. Include EVERY structural element, no matter how small. Do not skip any \
sections, appendices, or glossary entries.
5. Maintain document order — entries should appear in the same sequence as \
in the document.
6. For the document metadata, extract the title, version/edition, effective \
date if stated, and the issuing organization.

Be exhaustive. A missing entry means a gap in the knowledge graph. Every \
section and subsection heading in the document must appear as an entry."""


def build_phase2_prompt(
    section_number: str,
    page_start: int,
    page_end: int,
    profile: dict | None = None,
    schema: "SchemaSpec | None" = None,
    manifest: "ExtractionManifest | None" = None,
) -> str:
    """Generate the Phase 2 prompt for a specific section.

    When a SchemaSpec is provided, the prompt is entirely driven by the
    discovered node/edge types — no hardcoded extraction instructions.
    Falls back to generic extraction if no schema is available.

    When a manifest is provided, the prompt tells the LLM what nodes
    already exist so it can reference them instead of creating duplicates.
    """
    context = _profile_context(profile)
    manifest_context = manifest.to_prompt_fragment() if manifest else ""

    if schema:
        extraction_instructions = _schema_driven_instructions(schema)
    else:
        extraction_instructions = _generic_phase2_instructions()

    return f"""\
You are a document content analyst performing detailed extraction \
of Section {section_number} from this PDF document.
{context}
{manifest_context}

This PDF contains ONLY the pages for Section {section_number} \
(pages {page_start} through {page_end} of the original document). \
Extract everything you see in this PDF.

{extraction_instructions}

Respond with valid JSON. Structure your response as:
{{
  "section_id": "{section_number}",
  "elements": [
    {{
      "type": "<node type from the schema above>",
      "id": "<unique identifier — use the document's own numbering>",
      "properties": {{
        "<property_name>": "<value>",
        ...
      }},
      "relationships": [
        {{
          "type": "<edge type from the schema above>",
          "target_id": "<id of the target element>",
          "properties": {{}}
        }}
      ]
    }}
  ]
}}

Rules for the elements array:
- Every element MUST have a unique "id" using the document's own numbering \
(e.g., "11.2", "11.14(a)", "term:amortised_cost", "ref:IFRS_9").
- The "type" MUST match one of the node types listed in the schema above.
- Enrich every element with metadata that makes it useful in a knowledge graph. \
These properties are the node's identity in the graph — an agent will use them \
to navigate, query, and retrieve text from the PDF later. At minimum include:
  - "page_start": the page number as printed in the document where this element begins
  - "page_end": the page number where this element ends (if it spans multiple pages)
  - "semantic_role": what role this element plays (e.g., requirement, guidance, \
definition, exception, example, scope, heading, list_item)
  - "title": heading or label text if applicable
  - Any other properties from the schema that apply to this element type
- "relationships" captures edges TO other elements. Use the edge types from \
the schema. The target_id should be the id of another element (either in this \
section or elsewhere in the document).
- Include ALL elements — every paragraph, every cross-reference, every defined \
term, every table. Completeness is critical.
- Do NOT include verbatim text content. A tool extracts text from the PDF using \
the page_start metadata you provide. Your job is to discover and describe the \
structure — the what, where, and how elements relate to each other.
- Maintain document order."""


def _schema_driven_instructions(schema: "SchemaSpec") -> str:
    """Generate extraction instructions from SchemaSpec."""
    return f"""\
Extract ALL elements from this section according to the following \
knowledge graph schema (discovered from the document profile):

{schema.to_prompt_fragment()}

For each node type, create an element in the output with rich metadata. \
For each relationship type, add entries to the element's "relationships" array.

Your role is to discover structure and enrich each node with metadata that \
makes the knowledge graph useful. A separate tool handles text extraction \
from the PDF — you provide the page locations so it knows where to look. \
Do NOT copy verbatim text. Instead, focus on:
- Precise page locations (page_start, page_end)
- Semantic roles (requirement, guidance, definition, exception, etc.)
- Structural hierarchy and relationships between elements
- Cross-references to other sections, documents, and defined terms
- Any properties from the schema above that apply to each element

Be thorough: capture every structural element, every cross-reference, \
every defined term, every table. A missing element means a gap in the \
knowledge graph."""


def _generic_phase2_instructions() -> str:
    """Fallback instructions when no schema is available."""
    return """\
Extract the following structure (do NOT copy verbatim text — a tool does that):

1. PARAGRAPHS: Every paragraph in this section, in document order.
   - Use the exact paragraph number as printed
   - Record page_start (original document page number)
   - Identify the semantic role (requirement, guidance, definition, example, exception)
   - Note if list items are present

2. CROSS-REFERENCES: Every reference to another part of the document or \
to an external standard/law/document.
   - Provide a normalized target_id
   - Record which element contains the reference

3. DEFINED TERMS: Terms that have specific technical definitions.
   - Record the term name and which element defines it
   - List all elements where each term is used

4. TABLES: Any tables within this section.
   - Record structure: column headers, row count, page_start

Be thorough and precise. Every paragraph must be captured. Every cross-reference \
must be identified. Focus on structure and relationships — text extraction is \
handled separately."""

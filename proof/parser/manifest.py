"""Extraction manifest — tracks what already exists across chunks.

When extracting a document in chunks (section by section), each chunk
needs to know what nodes already exist so the LLM can:
  - REFERENCE existing nodes instead of creating duplicates
  - Create edges TO nodes in other chunks
  - Know what's already been extracted vs what's new

The manifest is built incrementally as chunks are processed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ExtractionManifest:
    """Tracks all extracted node IDs and their types across chunks."""

    # node_id → {"type": ..., "section": ..., "title": ...}
    nodes: dict[str, dict] = field(default_factory=dict)

    # Sections that have been fully extracted
    extracted_sections: list[str] = field(default_factory=list)

    def add_node(self, node_id: str, node_type: str, section: str = "", **extra: str) -> None:
        """Register a node as existing."""
        self.nodes[node_id] = {"type": node_type, "section": section, **extra}

    def add_from_outline(self, entries: list[dict]) -> None:
        """Add all outline entries to the manifest."""
        for entry in entries:
            node_id = f"s:{entry['number']}"
            self.add_node(
                node_id,
                node_type=entry.get("element_type", "section"),
                title=entry.get("title", ""),
            )

    def add_from_extraction(self, section_id: str, elements: list[dict]) -> None:
        """Add all elements from a chunk extraction to the manifest."""
        for el in elements:
            el_id = el.get("id", "")
            el_type = el.get("type", "unknown")
            if el_id:
                self.add_node(el_id, node_type=el_type, section=section_id)
        self.extracted_sections.append(section_id)

    def to_prompt_fragment(self) -> str:
        """Generate text describing existing nodes for injection into prompts."""
        if not self.nodes:
            return ""

        lines = [
            "",
            "--- EXISTING GRAPH NODES (do NOT create duplicates) ---",
            "",
            "The following nodes already exist in the knowledge graph from "
            "previous extraction passes. When you encounter references to "
            "these elements, use their EXISTING id as a target_id in "
            "relationships. Do NOT create new nodes for them.",
            "",
        ]

        # Group by type for readability
        by_type: dict[str, list[tuple[str, dict]]] = {}
        for node_id, info in self.nodes.items():
            t = info.get("type", "unknown")
            by_type.setdefault(t, []).append((node_id, info))

        for node_type, items in sorted(by_type.items()):
            lines.append(f"**{node_type}** ({len(items)} nodes):")
            # Show all IDs (they're short identifiers like "s:11", "11.2")
            for node_id, info in items[:50]:  # Cap at 50 per type for prompt size
                title = info.get("title", "")
                if title:
                    lines.append(f"  - {node_id}: {title}")
                else:
                    lines.append(f"  - {node_id}")
            if len(items) > 50:
                lines.append(f"  ... and {len(items) - 50} more")
            lines.append("")

        lines.append(
            "Sections already extracted in detail: "
            + (", ".join(self.extracted_sections) if self.extracted_sections else "(none)")
        )
        lines.append("--- END EXISTING NODES ---")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "extracted_sections": self.extracted_sections,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExtractionManifest:
        m = cls()
        m.nodes = data.get("nodes", {})
        m.extracted_sections = data.get("extracted_sections", [])
        return m

    def save(self, path) -> None:
        from pathlib import Path
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path) -> ExtractionManifest:
        from pathlib import Path
        data = json.loads(Path(path).read_text())
        return cls.from_dict(data)

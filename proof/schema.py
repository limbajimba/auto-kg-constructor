"""Step 3: Generate runtime KG schema from document profile.

Reads the profile's proposed_kg_schema and produces a SchemaSpec that
all downstream steps consume. No hardcoded node/edge types — everything
is data-driven from what the LLM discovered about the document.

If the profile lacks a proposed_kg_schema, makes an LLM call to generate
one from the rest of the profile.

Usage:
    uv run python -m proof.03_schema
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from proof.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    LOG_LEVEL,
    OUTPUT_DIR,
)

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema spec dataclasses
# ---------------------------------------------------------------------------

def _sanitize_label(name: str) -> str:
    """Turn a human-readable name into a valid Neo4j label (PascalCase, alphanum only)."""
    return re.sub(r"[^A-Za-z0-9]", "", name)


@dataclass
class NodeTypeSpec:
    name: str
    description: str
    properties: list[str] = field(default_factory=list)
    label: str = ""  # Neo4j label — auto-generated if empty

    def __post_init__(self) -> None:
        if not self.label:
            self.label = _sanitize_label(self.name)


@dataclass
class EdgeTypeSpec:
    name: str
    description: str
    properties: list[str] = field(default_factory=list)

    @property
    def rel_type(self) -> str:
        """Neo4j relationship type — UPPER_SNAKE_CASE."""
        return re.sub(r"[^A-Z0-9_]", "_", self.name.upper().replace(" ", "_"))


@dataclass
class SchemaSpec:
    node_types: list[NodeTypeSpec] = field(default_factory=list)
    edge_types: list[EdgeTypeSpec] = field(default_factory=list)

    # Lookup helpers
    def node_type(self, name: str) -> NodeTypeSpec | None:
        for nt in self.node_types:
            if nt.name == name:
                return nt
        return None

    def edge_type(self, name: str) -> EdgeTypeSpec | None:
        for et in self.edge_types:
            if et.name == name:
                return et
        return None

    def to_prompt_fragment(self) -> str:
        """Generate text describing the schema for injection into extraction prompts."""
        lines = ["## KG Schema (discovered from document profile)", ""]
        lines.append("### Node types to extract:")
        for nt in self.node_types:
            # Filter text_content — populated by text hydration tool, not LLM
            props = [p for p in nt.properties if p not in ("text_content", "content")]
            # Ensure location + semantic metadata is always listed
            for required in ("semantic_role", "page_end", "page_start"):
                if required not in props:
                    props.insert(0, required)
            props_str = ", ".join(props) if props else "page_start, page_end, semantic_role"
            lines.append(f"- **{nt.name}**: {nt.description}")
            lines.append(f"  Properties: {props_str}")
        lines.append("")
        lines.append("### Relationship types to extract:")
        for et in self.edge_types:
            props = ", ".join(et.properties) if et.properties else "(none)"
            lines.append(f"- **{et.name}**: {et.description}")
            lines.append(f"  Properties: {props}")
        return "\n".join(lines)

    def to_neo4j_constraints(self) -> list[str]:
        """Generate Cypher CREATE CONSTRAINT/INDEX statements."""
        stmts: list[str] = []
        for nt in self.node_types:
            label = nt.label
            stmts.append(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                f"REQUIRE n.id IS UNIQUE"
            )
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.id)"
            )
        return stmts

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SchemaSpec:
        return cls(
            node_types=[NodeTypeSpec(**nt) for nt in data.get("node_types", [])],
            edge_types=[EdgeTypeSpec(**et) for et in data.get("edge_types", [])],
        )


# ---------------------------------------------------------------------------
# Schema generation from profile
# ---------------------------------------------------------------------------

def generate_schema(profile: dict) -> SchemaSpec:
    """Extract SchemaSpec from profile's proposed_kg_schema.

    If the profile doesn't contain a proposed_kg_schema, calls the LLM
    to generate one from the rest of the profile.
    """
    proposed = profile.get("proposed_kg_schema")

    if proposed and proposed.get("node_types") and proposed.get("edge_types"):
        log.info("Building SchemaSpec from profile's proposed_kg_schema")
        return _schema_from_proposed(proposed)

    log.warning("Profile lacks proposed_kg_schema — generating via LLM")
    return _schema_via_llm(profile)


def _schema_from_proposed(proposed: dict) -> SchemaSpec:
    """Convert the profile's proposed_kg_schema dict into SchemaSpec."""
    node_types = []
    for nt in proposed.get("node_types", []):
        node_types.append(NodeTypeSpec(
            name=nt.get("node", nt.get("name", "Unknown")),
            description=nt.get("description", ""),
            properties=nt.get("properties", []),
        ))

    edge_types = []
    for et in proposed.get("edge_types", []):
        edge_types.append(EdgeTypeSpec(
            name=et.get("edge", et.get("name", "Unknown")),
            description=et.get("description", ""),
            properties=[
                p for p in et.get("properties", [])
                if isinstance(p, str)
            ],
        ))

    spec = SchemaSpec(node_types=node_types, edge_types=edge_types)
    log.info(
        "SchemaSpec: %d node types, %d edge types",
        len(spec.node_types), len(spec.edge_types),
    )
    for nt in spec.node_types:
        log.info("  Node: %s → :%s  (%s)", nt.name, nt.label, ", ".join(nt.properties) or "—")
    for et in spec.edge_types:
        log.info("  Edge: %s → :%s", et.name, et.rel_type)
    return spec


def _schema_via_llm(profile: dict) -> SchemaSpec:
    """Ask the LLM to propose a KG schema from the profile."""
    from google import genai

    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not set — cannot generate schema via LLM")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""You are a knowledge graph architect. Given this document profile,
propose node types and edge types for a structural knowledge graph.

IMPORTANT: The graph represents the DOCUMENT'S OWN STRUCTURE — sections,
paragraphs, cross-references, defined terms, etc. NOT extracted entities.

Document profile:
{json.dumps(profile, indent=2)}

Respond with valid JSON in this exact format:
{{
  "node_types": [
    {{"node": "TypeName", "description": "...", "properties": ["prop1", "prop2"]}}
  ],
  "edge_types": [
    {{"edge": "EDGE_NAME", "description": "...", "properties": ["prop1"]}}
  ]
}}
"""
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "temperature": 0.0},
    )
    proposed = json.loads(response.text)
    return _schema_from_proposed(proposed)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_schema(schema: SchemaSpec, output_dir: Path | None = None) -> Path:
    """Save SchemaSpec as kg_schema.json."""
    out = (output_dir or OUTPUT_DIR) / "kg_schema.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema.to_dict(), indent=2))
    log.info("Schema saved: %s", out)
    return out


def load_schema(output_dir: Path | None = None) -> SchemaSpec:
    """Load SchemaSpec from kg_schema.json."""
    path = (output_dir or OUTPUT_DIR) / "kg_schema.json"
    data = json.loads(path.read_text())
    return SchemaSpec.from_dict(data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== Step 3: Generate KG Schema from Profile ===")

    profile_path = OUTPUT_DIR / "document_profile.json"
    if not profile_path.exists():
        log.error("No profile found at %s — run 00_profile first", profile_path)
        sys.exit(1)

    profile = json.loads(profile_path.read_text())
    schema = generate_schema(profile)
    save_schema(schema)

    log.info("--- Prompt Fragment Preview ---")
    print(schema.to_prompt_fragment())

    log.info("--- Neo4j Constraints ---")
    for stmt in schema.to_neo4j_constraints():
        log.info("  %s", stmt)

    log.info("Done. Next step: uv run python -m proof.01_parse --sections 11")


if __name__ == "__main__":
    main()

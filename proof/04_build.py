"""Step 4: Build the knowledge graph in Neo4j from parsed data.

Run:  uv run python -m proof.04_build
      uv run python -m proof.04_build --clear  # wipe graph first

Prerequisites:
  - Neo4j running: docker compose up -d
  - Steps 00-03 completed (profile + schema + parse result exist)

This script reads the SchemaSpec and parse result, then creates nodes
and edges in Neo4j. ALL labels and relationship types come from the
SchemaSpec — nothing is hardcoded.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from neo4j import GraphDatabase

from proof.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER, OUTPUT_DIR
from proof.log import get_logger
from proof.schema import SchemaSpec, load_schema

log = get_logger("proof.04_build")


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


def _load_json(name: str) -> dict:
    path = OUTPUT_DIR / name
    if not path.exists():
        log.error("Missing %s — run earlier steps first", path)
        sys.exit(1)
    return json.loads(path.read_text())


def _sanitize_label(raw: str) -> str:
    """Sanitize a string for use as a Neo4j node label."""
    label = re.sub(r"[^A-Za-z0-9]", "", raw.replace(" ", ""))
    return label if label and len(label) <= 50 else "Element"


# --------------------------------------------------------------------------
# Generic node/edge creation
# --------------------------------------------------------------------------


def _create_node(tx, label: str, node_id: str, properties: dict) -> None:
    """Create a node with a dynamic label and arbitrary properties."""
    safe_label = _sanitize_label(label)
    # Filter out None values — Neo4j doesn't like null property values on CREATE
    clean_props = {k: v for k, v in properties.items() if v is not None}
    props_clause = ", ".join(f"{k}: ${k}" for k in clean_props)
    query = f"CREATE (n:{safe_label} {{id: $id, {props_clause}}})"
    tx.run(query, id=node_id, **clean_props)


def _merge_node(tx, label: str, node_id: str, properties: dict) -> None:
    """MERGE a node (create if not exists, update properties if exists)."""
    safe_label = _sanitize_label(label)
    clean_props = {k: v for k, v in properties.items() if v is not None}
    set_clause = ", ".join(f"n.{k} = ${k}" for k in clean_props)
    set_part = f"ON CREATE SET {set_clause} ON MATCH SET {set_clause}" if set_clause else ""
    query = f"MERGE (n:{safe_label} {{id: $id}}) {set_part}"
    tx.run(query, id=node_id, **clean_props)


def _create_edge(
    tx, source_id: str, target_id: str, edge_type: str, properties: dict | None = None
) -> int:
    """Create an edge with a dynamic type. Returns number of edges created."""
    safe_type = re.sub(r"[^A-Z0-9_]", "_", edge_type.upper().replace(" ", "_"))
    clean_props = {k: v for k, v in (properties or {}).items() if v is not None}
    props_clause = ", ".join(f"{k}: ${k}" for k in clean_props)
    props_part = f" {{{props_clause}}}" if props_clause else ""

    result = tx.run(
        f"""
        MATCH (a {{id: $src}})
        MATCH (b {{id: $tgt}})
        CREATE (a)-[:{safe_type}{props_part}]->(b)
        RETURN count(*) AS created
        """,
        src=source_id,
        tgt=target_id,
        **clean_props,
    )
    record = result.single()
    return record["created"] if record else 0


def _try_create_edge(
    tx, source_id: str, target_id: str, edge_type: str, properties: dict | None = None
) -> bool:
    """Try to create an edge. Returns False if either node doesn't exist."""
    safe_type = re.sub(r"[^A-Z0-9_]", "_", edge_type.upper().replace(" ", "_"))
    clean_props = {k: v for k, v in (properties or {}).items() if v is not None}
    props_clause = ", ".join(f"{k}: ${k}" for k in clean_props)
    props_part = f" {{{props_clause}}}" if props_clause else ""

    result = tx.run(
        f"""
        OPTIONAL MATCH (a {{id: $src}})
        OPTIONAL MATCH (b {{id: $tgt}})
        WITH a, b
        WHERE a IS NOT NULL AND b IS NOT NULL
        CREATE (a)-[:{safe_type}{props_part}]->(b)
        RETURN count(*) AS created
        """,
        src=source_id,
        tgt=target_id,
        **clean_props,
    )
    record = result.single()
    return record is not None and record["created"] > 0


# --------------------------------------------------------------------------
# Graph building from schema-less elements
# --------------------------------------------------------------------------


def _clear_graph(tx):
    """Delete all nodes and relationships."""
    tx.run("MATCH (n) DETACH DELETE n")


def _create_constraints(tx, schema: SchemaSpec) -> None:
    """Create uniqueness constraints and indexes from SchemaSpec."""
    for stmt in schema.to_neo4j_constraints():
        tx.run(stmt)


def _build_document_node(tx, profile: dict, outline_meta: dict, schema: SchemaSpec) -> None:
    """Create the root Document node using profile identity."""
    identity = profile.get("identity", {})
    doc_type = schema.node_type("Document")
    label = doc_type.label if doc_type else "Document"

    props = {
        "title": identity.get("title", outline_meta.get("title", "")),
        "issuer": identity.get("issuer", outline_meta.get("issuing_body", "")),
        "version": identity.get("date", outline_meta.get("version", "")),
        "domain": identity.get("domain", ""),
        "document_type": identity.get("document_type", outline_meta.get("document_type", "")),
        "total_pages": outline_meta.get("total_pages", 0),
    }
    _create_node(tx, label, "doc:root", props)


def _build_outline_nodes(tx, entries: list[dict], schema: SchemaSpec) -> None:
    """Create nodes for each outline entry using schema-appropriate labels."""
    structural = schema.node_type("StructuralElement")
    default_label = structural.label if structural else "StructuralElement"

    for entry in entries:
        # Use schema label if element_type matches a known node type,
        # otherwise use StructuralElement
        node_type = schema.node_type(entry["element_type"].title())
        label = node_type.label if node_type else default_label

        node_id = f"s:{entry['number']}"
        props = {
            "number": entry["number"],
            "title": entry["title"],
            "level": entry["level"],
            "element_type": entry["element_type"],
            "page_start": entry["page_start"],
            "page_end": entry["page_end"],
            "parent_number": entry.get("parent_number"),
        }
        _create_node(tx, label, node_id, props)


def _build_outline_edges(tx, entries: list[dict]) -> None:
    """Create HAS_PART and NEXT edges from outline hierarchy."""
    # HAS_PART: parent → child
    for entry in entries:
        parent = entry.get("parent_number")
        if parent:
            _create_edge(
                tx,
                source_id=f"s:{parent}",
                target_id=f"s:{entry['number']}",
                edge_type="HAS_PART",
                properties={"order": entry.get("page_start", 0)},
            )
        else:
            _create_edge(
                tx,
                source_id="doc:root",
                target_id=f"s:{entry['number']}",
                edge_type="HAS_PART",
                properties={"order": entry.get("page_start", 0)},
            )

    # NEXT: sequential siblings
    by_parent: dict[str | None, list[dict]] = {}
    for entry in entries:
        parent = entry.get("parent_number")
        by_parent.setdefault(parent, []).append(entry)

    for siblings in by_parent.values():
        siblings.sort(key=lambda e: e["page_start"])
        for i in range(len(siblings) - 1):
            _create_edge(
                tx,
                source_id=f"s:{siblings[i]['number']}",
                target_id=f"s:{siblings[i + 1]['number']}",
                edge_type="NEXT",
            )


def _build_section_elements(
    tx,
    section_details: list[dict],
    schema: SchemaSpec,
) -> list[dict]:
    """Build nodes and edges from schema-less elements arrays.

    Returns list of unresolved references (target node doesn't exist).
    """
    unresolved: list[dict] = []

    for sd in section_details:
        section_id = sd.get("section_id", "?")
        elements = sd.get("elements", [])

        # Track element order within section for NEXT edges
        prev_id_by_type: dict[str, str] = {}

        for i, el in enumerate(elements):
            el_type = el.get("type", "unknown")
            el_id = el.get("id", f"{section_id}:{i}")
            props = el.get("properties", {})

            # Look up label from schema
            node_spec = schema.node_type(el_type)
            label = node_spec.label if node_spec else _sanitize_label(el_type)

            # Always MERGE — elements may be referenced across chunks
            # before they're formally created, or may appear in multiple sections
            _merge_node(tx, label, el_id, props)

            # HAS_PART: section → element (for structural elements within a section)
            if el_type == "StructuralElement":
                _try_create_edge(
                    tx,
                    source_id=f"s:{section_id}",
                    target_id=el_id,
                    edge_type="HAS_PART",
                    properties={"order": i},
                )

                # NEXT between consecutive StructuralElements
                prev_key = f"StructuralElement"
                if prev_key in prev_id_by_type:
                    _create_edge(
                        tx,
                        source_id=prev_id_by_type[prev_key],
                        target_id=el_id,
                        edge_type="NEXT",
                    )
                prev_id_by_type[prev_key] = el_id

            # Create explicit relationships from the element
            for rel in el.get("relationships", []):
                rel_type = rel.get("type", "REFERENCES")
                target_id = rel.get("target_id", "")
                rel_props = rel.get("properties", {})

                if not target_id:
                    continue

                created = _try_create_edge(tx, el_id, target_id, rel_type, rel_props)
                if not created:
                    unresolved.append({
                        "source": el_id,
                        "target_id": target_id,
                        "rel_type": rel_type,
                        "element_type": el_type,
                        "section": section_id,
                    })

    return unresolved


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------


def _print_stats(driver):
    """Print graph statistics."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY count DESC
            """
        )
        log.info("--- Graph Nodes ---")
        total_nodes = 0
        for record in result:
            log.info("  %-25s %d", record["label"], record["count"])
            total_nodes += record["count"]
        log.info("  %-25s %d", "TOTAL", total_nodes)

        result = session.run(
            """
            MATCH ()-[r]->()
            RETURN type(r) AS type, count(r) AS count
            ORDER BY count DESC
            """
        )
        log.info("--- Graph Edges ---")
        total_edges = 0
        for record in result:
            log.info("  %-25s %d", record["type"], record["count"])
            total_edges += record["count"]
        log.info("  %-25s %d", "TOTAL", total_edges)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Build KG in Neo4j")
    parser.add_argument("--clear", action="store_true", help="Clear graph before building")
    args = parser.parse_args()

    log.info("=== Step 4: Build Knowledge Graph ===")

    # Load data
    profile = _load_json("document_profile.json")
    parse_result = _load_json("parse_result.json")
    schema = load_schema()

    outline = parse_result["outline"]
    entries = outline["entries"]
    section_details = parse_result.get("section_details", [])

    log.info(
        "Loaded: %d outline entries, %d section details, schema: %d node types / %d edge types",
        len(entries),
        len(section_details),
        len(schema.node_types),
        len(schema.edge_types),
    )

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    log.info("Connected to Neo4j at %s", NEO4J_URI)

    with driver.session() as session:
        if args.clear:
            log.info("Clearing existing graph...")
            session.execute_write(_clear_graph)

        log.info("Creating constraints from schema...")
        session.execute_write(_create_constraints, schema)

        log.info("Creating Document node...")
        session.execute_write(_build_document_node, profile, outline["metadata"], schema)

        log.info("Creating %d outline nodes...", len(entries))
        session.execute_write(_build_outline_nodes, entries, schema)

        log.info("Creating outline edges (HAS_PART + NEXT)...")
        session.execute_write(_build_outline_edges, entries)

        unresolved = []
        if section_details:
            total_elements = sum(len(sd.get("elements", [])) for sd in section_details)
            log.info("Creating %d section elements...", total_elements)
            unresolved = session.execute_write(
                _build_section_elements, section_details, schema
            )

    # Save unresolved references as actionable items for agent loop
    unresolved_path = OUTPUT_DIR / "unresolved_refs.json"
    if unresolved:
        unresolved_path.write_text(json.dumps(unresolved, indent=2))
        log.warning(
            "%d unresolved cross-references saved to %s — "
            "an agent can use these to decide what to extract next",
            len(unresolved),
            unresolved_path,
        )
    elif unresolved_path.exists():
        unresolved_path.unlink()

    # Stats
    _print_stats(driver)
    driver.close()

    log.info("Done. Next step: uv run python -m proof.05_query")
    log.info("Or browse: http://localhost:7474")


if __name__ == "__main__":
    main()

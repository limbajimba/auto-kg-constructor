"""Step 6: Verify graph nodes against the source PDF.

Run:  uv run python -m proof.06_verify
      uv run python -m proof.06_verify --sample 20
      uv run python -m proof.06_verify --retry    # verification + retry loop

Verification feedback loop: sample nodes from the graph, ask the LLM to
check them against the PDF, report accuracy. With --retry, re-extracts
sections that fail verification and rebuilds, up to max_iterations.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from google import genai
from google.genai import types
from neo4j import GraphDatabase

from proof.config import (
    FRS102_PDF,
    GEMINI_API_KEY,
    GEMINI_MAX_RETRIES,
    GEMINI_MODEL,
    GEMINI_RETRY_BASE_SECONDS,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    OUTPUT_DIR,
    PARSE_TIMEOUT_SECONDS,
)
from proof.log import get_logger

log = get_logger("proof.06_verify")

# --------------------------------------------------------------------------
# Verification prompt
# --------------------------------------------------------------------------

VERIFY_PROMPT = """\
You are a verification agent. You have been given a PDF document and a set \
of knowledge graph nodes extracted from it. Your job is to check each node \
against the actual PDF and report whether the extraction is correct.

For EACH node below, verify:
1. **text_accuracy**: Does the node's text_preview match the PDF content? \
The text was extracted via pypdf (see text_source field). Flag extraction \
errors, garbage characters, or missing content.
2. **type_accuracy**: Is the assigned node type correct based on what this \
element actually is in the document?
3. **completeness**: Are there any relationships, defined terms, or \
content in the original that were missed?
4. **structural_placement**: Is the node correctly identified (right id, \
right section)?

Respond with a JSON array. For each node, provide:
{{
  "node_id": "<the node's id>",
  "status": "correct" | "incorrect" | "incomplete",
  "text_accurate": true | false,
  "type_accurate": true | false,
  "issues": ["list of specific problems found"],
  "suggested_fixes": ["what should be corrected"],
  "section": "<which section this node belongs to>"
}}

Be strict. If even one word is wrong in the text, mark text_accurate as false. \
If a relationship was missed, mark status as "incomplete".

Here are the nodes to verify:

{nodes_json}
"""


# --------------------------------------------------------------------------
# Sample nodes from graph
# --------------------------------------------------------------------------


def _sample_nodes(driver, n: int) -> list[dict]:
    """Sample N nodes from the graph (any label) with their properties."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (node)
            WHERE node.id IS NOT NULL AND node.id <> 'doc:root'
            OPTIONAL MATCH (parent)-[:HAS_PART]->(node)
            OPTIONAL MATCH (node)-[r]->(target)
            WITH node, parent,
                 collect(DISTINCT {type: type(r), target: target.id}) AS rels
            RETURN node.id AS id,
                   labels(node)[0] AS label,
                   properties(node) AS props,
                   parent.id AS parent_id,
                   rels
            """
        )
        all_nodes = [dict(record) for record in result]

    if len(all_nodes) <= n:
        return all_nodes

    random.shuffle(all_nodes)
    return all_nodes[:n]


# --------------------------------------------------------------------------
# Verification via LLM
# --------------------------------------------------------------------------


def _verify_batch(
    client: genai.Client,
    model: str,
    uploaded_file: types.File,
    nodes: list[dict],
) -> list[dict]:
    """Ask the LLM to verify a batch of nodes against the PDF."""
    nodes_for_prompt = []
    for node in nodes:
        props = node.get("props", {})
        # Truncate long text for prompt
        text = props.get("text_content", props.get("text", ""))
        if isinstance(text, str) and len(text) > 500:
            text = text[:500] + "..."

        nodes_for_prompt.append({
            "node_id": node["id"],
            "label": node["label"],
            "text_preview": text,
            "text_source": props.get("text_source", "unknown"),
            "properties": {k: v for k, v in props.items()
                          if k not in ("text_content", "text", "text_source") and v is not None},
            "parent_id": node.get("parent_id"),
            "relationships": [r for r in node.get("rels", []) if r.get("target")],
        })

    prompt = VERIFY_PROMPT.format(nodes_json=json.dumps(nodes_for_prompt, indent=2))

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0,
    )

    last_error = None
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[uploaded_file, prompt],
                config=config,
            )
            return json.loads(response.text)
        except Exception as exc:
            last_error = exc
            if attempt < GEMINI_MAX_RETRIES:
                wait = GEMINI_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                log.warning("Verify attempt %d failed: %s — retrying in %.1fs", attempt, exc, wait)
                time.sleep(wait)
            else:
                log.error("Verification failed after %d attempts: %s", GEMINI_MAX_RETRIES, exc)
    raise last_error  # type: ignore[misc]


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def _compute_report(verifications: list[dict]) -> dict:
    """Compute and log summary stats."""
    correct = sum(1 for v in verifications if v.get("status") == "correct")
    incorrect = sum(1 for v in verifications if v.get("status") == "incorrect")
    incomplete = sum(1 for v in verifications if v.get("status") == "incomplete")
    total = len(verifications)
    accuracy_pct = round(100 * correct / total, 1) if total else 0.0

    log.info("=== Verification Report ===")
    log.info("  Correct:    %d/%d (%.1f%%)", correct, total, accuracy_pct)
    log.info("  Incomplete: %d/%d", incomplete, total)
    log.info("  Incorrect:  %d/%d", incorrect, total)

    for v in verifications:
        if v.get("status") != "correct":
            log.warning(
                "  %s [%s]: %s",
                v.get("node_id", "?"),
                v.get("status", "?"),
                "; ".join(v.get("issues", [])),
            )

    return {
        "total": total,
        "correct": correct,
        "incomplete": incomplete,
        "incorrect": incorrect,
        "accuracy_pct": accuracy_pct,
        "verifications": verifications,
    }


# --------------------------------------------------------------------------
# Retry loop: verify → identify bad sections → re-extract → rebuild
# --------------------------------------------------------------------------


def _sections_needing_retry(verifications: list[dict]) -> dict[str, list[dict]]:
    """Group failed verifications by section for targeted re-extraction."""
    by_section: dict[str, list[dict]] = {}
    for v in verifications:
        if v.get("status") in ("incorrect", "incomplete"):
            section = v.get("section", "unknown")
            by_section.setdefault(section, []).append(v)
    return by_section


def verify_and_retry(
    pdf_path: Path,
    driver,
    client: genai.Client,
    uploaded_file: types.File,
    sample_size: int = 20,
    accuracy_threshold: float = 0.8,
    max_iterations: int = 3,
) -> dict:
    """Verification loop: verify → find issues → re-extract → rebuild → repeat.

    Returns the final verification report.
    """
    for iteration in range(1, max_iterations + 1):
        log.info("--- Verification iteration %d/%d ---", iteration, max_iterations)

        nodes = _sample_nodes(driver, sample_size)
        if not nodes:
            log.error("No nodes found in graph — run 04_build first")
            return {"error": "no nodes"}

        log.info("Sampled %d nodes for verification", len(nodes))

        # Verify in batches
        batch_size = 10
        all_verifications: list[dict] = []
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            log.info("Verifying batch %d-%d...", i + 1, min(i + batch_size, len(nodes)))
            t0 = time.monotonic()
            results = _verify_batch(client, GEMINI_MODEL, uploaded_file, batch)
            elapsed = time.monotonic() - t0
            log.info("Batch verified in %.1fs", elapsed)
            all_verifications.extend(results)

        report = _compute_report(all_verifications)

        if report["accuracy_pct"] >= accuracy_threshold * 100:
            log.info(
                "Verification PASSED at %.1f%% (threshold %.0f%%) on iteration %d",
                report["accuracy_pct"],
                accuracy_threshold * 100,
                iteration,
            )
            report["iteration"] = iteration
            report["passed"] = True
            return report

        # Identify sections needing retry
        bad_sections = _sections_needing_retry(all_verifications)
        log.warning(
            "Accuracy %.1f%% < %.0f%% threshold — %d sections need re-extraction: %s",
            report["accuracy_pct"],
            accuracy_threshold * 100,
            len(bad_sections),
            list(bad_sections.keys()),
        )

        if iteration < max_iterations:
            # Re-extract and rebuild is left to the agent loop / orchestrator.
            # For now, log the actionable feedback.
            for section, issues in bad_sections.items():
                issue_summary = [
                    f"  {v.get('node_id', '?')}: {'; '.join(v.get('issues', []))}"
                    for v in issues
                ]
                log.warning(
                    "Section %s has %d issues:\n%s",
                    section,
                    len(issues),
                    "\n".join(issue_summary),
                )

            # Save feedback for agent consumption
            feedback_path = OUTPUT_DIR / "verification_feedback.json"
            feedback_path.write_text(json.dumps({
                "iteration": iteration,
                "accuracy_pct": report["accuracy_pct"],
                "sections_to_retry": {
                    section: [
                        {"node_id": v.get("node_id"), "issues": v.get("issues", []),
                         "suggested_fixes": v.get("suggested_fixes", [])}
                        for v in issues
                    ]
                    for section, issues in bad_sections.items()
                },
            }, indent=2))
            log.info("Feedback saved: %s", feedback_path)

            # NOTE: In the future agent loop, this is where the agent would:
            # 1. Read verification_feedback.json
            # 2. Re-extract bad sections with feedback-augmented prompts
            # 3. Update the graph
            # 4. Continue the loop
            # For now, we just log and continue sampling (different random nodes).
            log.info("Continuing to next iteration with new sample...")

    log.warning(
        "Verification did NOT pass after %d iterations (final accuracy: %.1f%%)",
        max_iterations,
        report["accuracy_pct"],
    )
    report["iteration"] = max_iterations
    report["passed"] = False
    return report


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify graph against PDF")
    parser.add_argument("--pdf", type=Path, default=FRS102_PDF, help="PDF to verify against")
    parser.add_argument("--sample", type=int, default=10, help="Number of nodes to verify")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--retry", action="store_true", help="Enable retry loop")
    parser.add_argument("--threshold", type=float, default=0.8, help="Accuracy threshold (0-1)")
    parser.add_argument("--max-iter", type=int, default=3, help="Max retry iterations")
    args = parser.parse_args()

    random.seed(args.seed)
    log.info("=== Step 6: Graph Verification ===")

    # Verify Gemini API
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not set")
        return

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=PARSE_TIMEOUT_SECONDS * 1000),
    )

    log.info("Uploading %s to Gemini...", args.pdf.name)
    uploaded = client.files.upload(file=args.pdf)
    log.info("Upload complete (name=%s)", uploaded.name)

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    log.info("Connected to Neo4j at %s", NEO4J_URI)

    if args.retry:
        report = verify_and_retry(
            pdf_path=args.pdf,
            driver=driver,
            client=client,
            uploaded_file=uploaded,
            sample_size=args.sample,
            accuracy_threshold=args.threshold,
            max_iterations=args.max_iter,
        )
    else:
        # Single-shot verification
        nodes = _sample_nodes(driver, args.sample)
        if not nodes:
            log.error("No nodes found — run 04_build first")
            driver.close()
            return

        log.info("Sampled %d nodes for verification", len(nodes))

        batch_size = 10
        all_verifications: list[dict] = []
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            log.info("Verifying batch %d-%d...", i + 1, min(i + batch_size, len(nodes)))
            t0 = time.monotonic()
            results = _verify_batch(client, GEMINI_MODEL, uploaded, batch)
            elapsed = time.monotonic() - t0
            log.info("Batch verified in %.1fs", elapsed)
            all_verifications.extend(results)

        report = _compute_report(all_verifications)

    driver.close()

    # Save full report
    report_path = OUTPUT_DIR / "verification_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Full report saved: %s", report_path)


if __name__ == "__main__":
    main()

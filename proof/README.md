# Proof of Concept: Can we faithfully represent document structure as a knowledge graph?

## Hypothesis

An authoritative document's own structure (hierarchy, cross-references, defined
terms, formatting semantics) can be captured as a knowledge graph where:
- Nodes = structural elements (sections, paragraphs, tables, defined terms)
- Edges = structural relationships (parent-child, cross-reference, definition-usage)
- The graph enables deterministic, reproducible answers to questions about the document

## Test Document

**FRS 102 — The Financial Reporting Standard applicable in the UK and Republic of Ireland**

We start with Section 11 (Basic Financial Instruments) because it has:
- Clear hierarchical structure (section → subsections → paragraphs)
- Cross-references to other sections ("see Section 12")
- Defined terms ("financial instrument", "amortised cost")
- Formatting semantics (bold = requirements)
- Manageable size (~20 pages)

## Steps

| Script | What it does | What we learn |
|--------|-------------|---------------|
| `01_parse.py` | Parse FRS 102 PDF with Docling | What does Docling actually give us? Hierarchy depth, formatting preservation, structure fidelity |
| `02_inspect.py` | Inspect and map Docling output | How does Docling's model map to our ontology needs? What's missing? What's extra? |
| `03_schema.py` | Define the KG schema against real data | The core ontology — validated against what we actually parsed, not imagined |
| `04_build.py` | Build Section 11 as a graph in Neo4j | Can we faithfully represent the structure? What breaks? |
| `05_query.py` | Query the graph with real questions | Can we deterministically answer: "What are the recognition criteria for financial instruments?" |

## Success Criteria

1. Every paragraph in Section 11 has exactly one node (zero missing, zero duplicated)
2. Hierarchy matches the document (parent-child relationships are correct)
3. Cross-references resolve to correct target nodes
4. A consumer can navigate the graph to answer domain questions without the original PDF

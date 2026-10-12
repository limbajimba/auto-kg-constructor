# Auto KG Constructor

## Problem Statement

Take any authoritative document corpus → produce a perfectly representative
structured backend + clean APIs → so any AI agent can reason over that corpus
as well as a human expert who studied it for years.

## Vision

Imagine a long-running desktop agent (like OpenClaw). A scraper agent has
collected quarterly earnings reports, regulatory filings, or technical manuals.
Dumping all those PDFs into an LLM context is not viable. Instead, this system
autodiscovers the structure of each document, builds a traversable knowledge
graph, and exposes it as a tool that other AI agents can navigate — like a
human expert with years of study.

This is the POC for that.

## Core Philosophy

1. **Structure IS knowledge** — nodes are structural elements (sections,
   paragraphs, articles), not extracted entities. Edges are structural
   relationships (hierarchy, cross-references, definitions).
2. **Autodiscovery, not hardcoding** — the system should explore any unknown
   document, discover its structure, and decide how to represent it. We give
   minimal guidance. No rigid Pydantic schemas dictating what the LLM should
   find. The LLM tells US what it found.
3. **Prove with real data before abstracting** — build for one document first
   (FRS 102), then generalise.
4. **Deterministic retrieval** — rule-based navigation over the graph, not
   similarity search. Like PageIndex but producing a graph, not just a tree.

## Reference Architecture: PageIndex Pattern

PageIndex (github.com/VectifyAI/PageIndex) validates our approach:
- Scans document → detects if TOC exists → 3 adaptive paths
- No predefined schema — LLM decides the structure
- Recursive sub-structure discovery (start coarse, refine where needed)
- Verification loop (check LLM's work against actual document)

**Where we go further than PageIndex:**
- PageIndex builds a tree (parent-child). We build a graph (cross-refs,
  defined terms, temporal relationships, external references).
- PageIndex is retrieval-focused. We produce a structural backend/tool.
- We capture semantic roles, formatting conventions, relationship patterns.
- We handle multi-document corpora with versioning (SAT-Graph RAG Work vs
  Expression model).

## Current Phase: Proof of Concept

Proving the core hypothesis with FRS 102 (Section 11). Code lives in `proof/`.

### What's Built

- **Gemini parser** (`proof/parser/`): Two-phase extraction via Gemini 2.5 Pro
  - Phase 1: Document outline (hierarchy, page ranges)
  - Phase 2: Section detail (paragraphs, cross-refs, terms, tables)
  - SHA-256 caching, retry logic, parser protocol abstraction
- **KG schema** (`proof/03_schema.py`): SAT-Graph RAG inspired ontology
  (currently hardcoded — needs to become dynamic)
- **Tests**: 16 passing (parser models, cache, schema)

### What's Next: Document Self-Discovery

The current parser uses hardcoded extraction schemas. The next step is adding
a profiling/discovery phase that:

1. Uploads PDF → asks LLM open-ended questions ("what is this document? how
   is it structured? what patterns exist?")
2. Stores the free-form discovery as the document profile
3. Uses that profile to drive adaptive extraction prompts
4. Makes KG node/edge types data-driven (discovered), not code enums

Key insight from research: AutoSchemaKG achieves 95% alignment with human
schemas using zero predefined types. GraphRAG's auto-tuning samples 1% of
corpus to generate domain-adapted prompts. Both validate the autodiscovery
approach.

### Proof Sequence

```
00_profile  → Document self-discovery (free-form LLM exploration)
01_parse    → Adaptive extraction (driven by profile)
02_inspect  → Quality validation
03_schema   → Dynamic KG schema (from profile, not hardcoded)
04_build    → Neo4j graph construction
05_query    → Query validation (can agents answer real questions?)
```

## Architecture

- **Parsing/Discovery**: Gemini 2.5 Pro (native PDF vision, structured output)
- **Graph storage**: Neo4j Community Edition (Docker)
- **Runtime**: Claude Agent SDK (future — execution + orchestration)
- **Output API**: MCP servers (future — after proof)
- **Ontology basis**: SAT-Graph RAG (Work vs Expression, bi-temporal)

## Commands

```bash
docker compose up -d                                # Start Neo4j
uv sync                                             # Install deps
uv sync --extra dev                                 # Install dev tools
uv run python -m proof.00_profile                   # Profile document
uv run python -m proof.01_parse --sections 11       # Parse section 11
uv run python -m proof.02_inspect                   # Inspect results
uv run pytest                                       # Run tests
```

## Key Technical Decisions

- **Gemini 2.5 Pro** over Docling: Native PDF vision, structured output via
  Pydantic, ~$2-3 per full document parse. Docling was 20+ min on CPU.
- **Two-phase extraction**: Outline first (all sections), then detail per
  section. Needed because Gemini has ~65K output token limit.
- **No Pydantic defaults in extraction models**: Gemini's response_schema
  constraint. All optional fields use Optional[T].
- **ParserProtocol**: typing.Protocol so backends are swappable (Gemini today,
  Claude/local models tomorrow).
- **SHA-256 cache**: Per-phase/section, auto-invalidates when PDF changes.

## Core Architecture: Tool Call + Feedback Loops (OpenClaw Pattern)

The entire system should be agent-driven with tool call + feedback loops,
NOT one-shot procedural scripts. Every operation returns feedback that the
agent reasons about:

- Agent calls tool: "Create edge p11.2 → Section 12"
- Tool responds: "Target node 'Section 12' doesn't exist"
- Agent reasons: "I need to extract Section 12 first"
- Agent calls parser tool for Section 12
- Agent retries the edge creation
- Tool responds: "Edge created"

This applies to EVERY step: profiling, extraction, graph building, querying.
The agent loop discovers what's missing and fills gaps autonomously. This is
how you get completeness and correctness — not by hardcoding every edge case,
but by letting the agent react to feedback.

Current POC is procedural scripts. The path to production is converting each
step into tools that agents call, with structured feedback on every operation.

## Future: Autonomous Discovery Agent

The current 00_profile is a single LLM call. The vision is a proper autonomous
agent with a tool loop:

- **Discovery agent** with tools: sample pages, read TOC, inspect formatting,
  check cross-references, examine glossary, etc. Iterates until confident it
  understands the document. For large corpora this matters — one pass won't
  catch everything.
- **Verification agent** that reviews the discovery agent's output: checks
  claims against actual document content, flags gaps, scores confidence. This
  is critical because all downstream agents depend on accurate profiling.
- **Feedback loop**: verification findings feed back into discovery for
  refinement. The profile is only "locked" when verification passes.

This matters most for large/complex corpora where a single LLM call can't
see everything. The POC proves the concept with one call; the agent loop
scales it.

## Anti-Patterns to Avoid

- **Hardcoded type enums** — don't define NodeType/EdgeType as Python StrEnums.
  Types should be discovered from the document and stored as data.
- **Rigid profiling schemas** — don't create Pydantic models that dictate what
  the LLM should discover. Let the LLM explore freely, store what it finds.
- **Over-engineering** — this is a POC. Build the minimum that proves the
  hypothesis, then iterate.
- **Entity extraction KG** — we're not building a traditional NER→KG pipeline.
  The document's own structure IS the graph.

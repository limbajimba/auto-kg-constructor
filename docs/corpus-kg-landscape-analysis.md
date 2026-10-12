# Corpus-to-Knowledge-Graph System: Landscape Analysis & Gap Assessment

## The Problem Statement (Crisp)

**We are building an AI engineering team (agents + tools) that takes any authoritative document corpus, develops deep understanding of it, and produces a perfectly representative structured backend with clean APIs — so any other AI agent can reason over that corpus as well as a human expert who studied it for years.**

The system is Layer A (construction crew). The output serves Layer B (tenants). Our job is the building, not the occupants.

---

## What Already Exists: The Landscape

### 1. Document Parsing & Structure Extraction

**The strongest area. Lots of good tools exist here.**

| Tool | What It Does | Strengths | Gaps for Us |
|------|-------------|-----------|-------------|
| **Docling (IBM)** | Converts PDFs → structured DoclingDocument with hierarchy, tables, reading order | Best open-source parser. Preserves section hierarchy. DocTags format is purpose-built for structure. 258M param VLM. | Output is document-level. No corpus-level relationships. No cross-reference resolution. No KG construction. |
| **Docling-Graph (IBM)** | Extends Docling → knowledge graph via Pydantic templates | Template-driven extraction. Multi-stage passes. Neo4j/ArangoDB export. | Requires pre-defined Pydantic schemas — someone must define the template. Not self-discovering. Entity-relationship extraction, not document structure preservation. |
| **PageIndex (VectifyAI)** | Builds hierarchical tree index (ToC-like JSON) from documents. Reasoning-based retrieval via tree search. | Exactly the right retrieval model — structure-based navigation, not vector similarity. 98.7% accuracy on FinanceBench. MCP server available. MIT licensed. | Single-document scope. No cross-document relationships. No temporal versioning. No cross-reference extraction. Tree is for retrieval, not knowledge representation. |
| **Contextual AI Parser** | Document-level hierarchy inference for RAG | Understands how page 5 contextualizes page 237. Good at inferring hierarchy even without explicit headers. | Closed-source/API. Not a KG system. |
| **LandingAI ADE** | Agentic document extraction with self-correction loops | ReAct-style agent that reviews and corrects its own extraction. | Focused on data extraction (fields from forms), not corpus representation. |
| **Reducto** | Structure-aware document parsing for RAG | Semantic chunking. Good at tables and mixed layouts. | Parsing tool, not a representation system. |

**Key Insight**: Parsing is a solved-ish problem. Docling + PageIndex between them handle the two hardest parts — faithful structural extraction and structure-based retrieval. What nobody has built is the bridge from "parsed single document" to "navigable, addressable, temporally-versioned, cross-referenced knowledge graph of an entire corpus."

### 2. Knowledge Graph Construction from Documents

**Lots of activity, but almost all focused on entity-relationship extraction, not document structure preservation.**

| System | Approach | Gap for Us |
|--------|----------|------------|
| **LangChain LLM Graph Transformer** | LLM extracts entities and relationships → Neo4j | Generic entity extraction. Doesn't preserve document hierarchy. Schema must be pre-defined or auto-detected. |
| **KARMA (Multi-agent KG enrichment)** | 9 specialised agents: ingestion, reading, summarization, entity extraction, relationship extraction, schema alignment, conflict resolution | Closest to our multi-agent architecture, but focused on enriching *existing* KGs with new triples from papers. Not about representing document structure. |
| **Microsoft GraphRAG** | Community detection, hierarchical summarization of document chunks | Creates communities and summaries, not faithful document representations. Designed for query answering, not as a navigation index. |
| **AutoSchemaKG (HKUST)** | Autonomous KG construction without predefined schemas | Research framework. Processed 50M documents. But outputs are entity-relationship triples, not structural representations. |
| **FalkorDB GraphRAG SDK** | Document → queryable knowledge graph pipeline | Production-focused but same entity-extraction paradigm. |

**Key Insight**: The entire KG construction space thinks about documents as containers of entities and relationships to extract. Nobody treats the document's own structure — its hierarchy, cross-references, defined terms, formatting semantics — as the primary knowledge to preserve. Everyone is looking *through* the document at the world it describes. We need to look *at* the document itself.

### 3. Legal/Regulatory Document-Specific Systems

**The closest academic work to what we need.**

| Paper/System | Innovation | Gap for Us |
|-------------|-----------|------------|
| **SAT-Graph RAG** (arXiv 2505.00039) | Ontology-driven GraphRAG for legal norms. Distinguishes abstract Works from versioned Expressions. Temporal states. Legislative events as first-class nodes. Planner-guided deterministic query resolution. | Most directly relevant research. But it's a research paper, not a system. Focused on Brazilian legal norms. Not automated — requires manual ontology setup. |
| **WhyHow + Reducto Legal RAG** | Multi-graph multi-agent retrieval for legal documents. Separate document hierarchy graph + definition graph. Recursive cross-reference resolution. | Great demonstration of the right retrieval pattern for legal docs. But manually constructed, not automatically generated from corpus. |
| **Graphwise** | Semantic knowledge graphs for regulatory compliance (DORA). Taxonomy management. Definition extraction. | Commercial product. Right problem space. But manual graph construction with LLM assistance, not autonomous agent system. |

**Key Insight**: The SAT-Graph RAG paper is the closest thing to our vision in terms of *what* the graph should look like — bi-temporal, hierarchy-preserving, with legislative events as first-class entities. But it's all manual construction. Nobody has built agents that *automatically* produce this kind of graph.

### 4. Agent Memory & Learning Systems

**For our engineering agents' own learning and memory.**

| System | What It Does | Relevance |
|--------|-------------|-----------|
| **Supermemory** | Memory API for AI agents. User profiles, episodic memory, project knowledge. State-of-art on LongMemEval. MCP integration. OpenClaw plugin. | Could be our engineering agents' memory backend. Handles temporal reasoning (76.69%). But it's a general-purpose memory system, not specialised for engineering learning patterns. |
| **Mem0** | Universal memory layer. Extracts and stores memories from conversations. Vector + graph. | Simpler than Supermemory. Good for basic memory. Less temporal sophistication. |
| **Zep/Graphiti** | Temporal knowledge graph for agent memory. Bi-temporal model. Incremental updates. | Best for evolving knowledge with temporal awareness. Could store engineering agents' evolving understanding of a corpus. |
| **Hindsight** | Four epistemically-distinct memory networks. TEMPR + CARA. 91.4% on LongMemEval. | Research paper. Most theoretically complete memory system. Distinguishes facts from beliefs, tracks confidence. Not implemented as product. |

### 5. Agent Frameworks & Infrastructure

**For how our engineering agents operate.**

| Framework | Model | Relevance |
|-----------|-------|-----------|
| **OpenClaw** | Persistent daemon. Skills as SKILL.md + YAML. Local-first. Shell access. Self-improving. | Exactly the paradigm Nitanshu described — agents defined in YAML, guidance in .md files, access to their own "computer." Skills are portable, community-shared. Would need heavy customisation for our domain. |
| **mcp-agent** | MCP-native agent patterns (map-reduce, orchestrator, evaluator-optimizer). Temporal backend for durability. | Good patterns library. The evaluator-optimizer pattern maps to our validation loops. Temporal backend handles long-running KG construction jobs. |
| **Claude Code / Anthropic Skills** | Agents with computer access, skills as SKILL.md files, local execution. | Our engineering agents could literally be Claude Code instances with domain-specific skills. The skill format is proven at scale. |

---

## The Gap: What Doesn't Exist

After surveying everything, here is what **nobody has built**:

### Gap 1: Autonomous Corpus Profiler
No system exists that takes an arbitrary document corpus and automatically discovers: what kind of documents these are, what structural patterns they follow, what numbering schemes they use, how cross-references work, what formatting carries semantic meaning, and what the glossary/definition conventions are.

Everyone either (a) requires manual schema/template definition, or (b) treats all documents the same way (generic chunking + entity extraction).

### Gap 2: Document Structure as First-Class Knowledge
Every KG construction system treats document structure as scaffolding to be discarded. They extract entities and relationships *from* the text, then throw away the hierarchy. Nobody builds a KG where the primary nodes ARE the structural elements (sections, paragraphs, defined terms, tables) and the primary edges ARE the structural relationships (parent-child, cross-reference, definition-usage, amendment-chain).

PageIndex comes closest — it preserves hierarchy as a tree — but it's a retrieval index, not a knowledge graph. It doesn't capture cross-references, defined terms, formatting semantics, or temporal versions.

### Gap 3: Automated API/Tool Generation from KG
Nobody builds the step from "here's a knowledge graph" to "here are the MCP tools/APIs that let an agent navigate this specific corpus." The API surface should be tailored to the corpus type — a regulatory standard needs different primitives than a medical textbook. This step is entirely manual today.

### Gap 4: Bi-Temporal Corpus Management via Agents
The SAT-Graph RAG paper describes what bi-temporal legal document graphs should look like. Graphiti/Zep describe how to do bi-temporal updates. But nobody has built agents that can take an amendment document, understand what it changes, and surgically update an existing KG while preserving historical versions.

### Gap 5: Engineering Agent Learning Loop
No system exists where agents that build KGs from documents get better at it over time. Every pipeline today is stateless — it processes the 100th document exactly the same way as the first. The patterns, strategies, and failure modes discovered during processing are thrown away.

### Gap 6: Cross-Corpus Linking
While multi-document search exists, no system automatically discovers and creates typed cross-corpus edges (e.g., "FRS 102 Section 12 references IFRS for SMEs Section 11" or "Companies Act 2006 s.393 constrains FRS 102 Section 3").

---

## What We Can Leverage vs. What We Must Build

### LEVERAGE (Don't Reinvent)

| Component | Use | Why |
|-----------|-----|-----|
| **Docling** | Document parsing layer | Best open-source parser. Handles PDF → structured hierarchy. DocTags preserve structure faithfully. Active IBM backing. |
| **PageIndex** | Tree index generation & retrieval model | Proven approach to structure-based retrieval. MIT licensed. Can be extended. Their OCR preserves hierarchy. |
| **Neo4j or similar** | Graph storage | Mature, well-tooled. Cypher query language. Community support. |
| **Supermemory or Zep/Graphiti** | Engineering agent memory | Don't build memory from scratch. Use existing temporal memory system. Supermemory has best benchmarks; Zep has best temporal model. Evaluate both. |
| **OpenClaw / Claude Code skill format** | Agent definition pattern | YAML + SKILL.md is proven at massive scale. Portable. Community understands it. Don't invent a new agent definition format. |
| **MCP** | Output API standard | The standard for agent-to-tool communication. Our output should be MCP servers, not custom APIs. |

### BUILD (Novel Components)

| Component | Why It's Novel | Priority |
|-----------|---------------|----------|
| **Corpus Profiler Agent** | Examines corpus, discovers document types, structural patterns, cross-reference syntax, formatting semantics. No existing system does this. | P0 — everything depends on it |
| **Structure-Preserving KG Schema** | A graph schema where nodes = structural elements (sections, paragraphs, terms, tables) and edges = structural relationships (hierarchy, cross-ref, definition, amendment). Different from all existing entity-extraction KG schemas. | P0 — core data model |
| **Pipeline Generator Agent** | Takes profiler output and generates deterministic extraction code (regex for cross-refs, parsers for numbering schemes, validators for structure). The "LLM as software engineer" concept. | P0 — the core innovation |
| **Cross-Reference Resolver** | Extracts and resolves all cross-references into typed edges in the KG. Handles internal (paragraph-to-paragraph) and external (corpus-to-corpus) references. | P1 — critical for regulatory documents |
| **Temporal Version Manager** | Handles amendments, effective dates, supersession chains. Bi-temporal model with valid_from/valid_until on nodes and edges. | P1 — needed before any real corpus can be maintained |
| **MCP Server Generator** | Takes a completed KG and auto-generates an MCP server with corpus-specific tools (get_toc, get_section, get_definition, resolve_reference, search, etc.) | P1 — the output product |
| **Validation Framework** | Multi-pass validation: structural checks, LLM sampling, functional tests, completeness metrics. | P1 — differentiator for quality |
| **Agent Learning System** | Captures patterns, strategies, failures from each corpus onboarding. Uses existing memory system but with domain-specific schema for engineering knowledge. | P2 — makes system improve over time |

---

## Architectural Approaches to Consider

### 1. The SAT-Graph RAG Model (for our KG schema)
The most relevant academic architecture. Key ideas to adopt:
- **Works vs. Expressions**: Distinguish abstract document (FRS 102) from specific version (FRS 102 January 2022 edition). This is the bi-temporal foundation.
- **Legislative Events as First-Class Nodes**: When FRC publishes amendment, that's a node connected to affected paragraphs. Makes the "why did this change?" query answerable.
- **Hierarchy as Community Structure**: Don't use algorithmic community detection for regulatory docs — the hierarchy IS the community structure, curated by domain experts.
- **Deterministic Query Resolution**: For regulatory compliance, you need deterministic (reproducible) answers, not probabilistic (different-every-time) ones. The retrieval layer should be rule-based, not similarity-based.

### 2. PageIndex-Style Tree as Primary Interface
- Tree structure generated by agent during profiling/extraction
- Stored in KG but also available as JSON for in-context reasoning
- Consumer agent reads tree, reasons about where to look, navigates
- Fallback to search only when agent genuinely doesn't know where to look

### 3. OpenClaw-Style Agent Architecture
For our engineering agents:
- Each agent defined by YAML (identity, capabilities, constraints)
- Guidance in SKILL.md files (how to profile documents, how to extract structure, how to validate)
- Access to sandboxed compute environment (can run code, test extractions, validate output)
- Memory via Supermemory or Zep (persists learning across corpus onboarding sessions)
- Agents can create new skills (if they discover a new document pattern, they can write a SKILL.md for it)

### 4. Separate Graph Per Corpus with Cross-Corpus Edges
- Each corpus gets its own graph instance
- Cross-corpus references become typed edges (reference_type: "external", source_corpus: "frs_102", target_corpus: "companies_act_2006")
- Each graph independently versionable and updatable
- Consumer agents query across graphs via unified MCP interface

---

## The Hard Technical Problems

### 1. Parsing Fidelity for Regulatory Documents
FRS 102 uses bold text for requirements, non-bold for guidance. This distinction is legally significant. Most parsers strip formatting. Docling preserves some formatting via DocTags, but the "bold = requirement" semantic layer needs custom extraction.

### 2. Cross-Reference Resolution Is NP-Hard in General
References like "see paragraph 12.3" are easy. References like "the exemptions described in Section 12" are medium. References like "the accounting policy required by this section" are hard — they're contextual. References to external standards ("as defined in IFRS for SMEs") cross corpus boundaries and may not have been onboarded yet.

Strategy: Start with deterministic (regex-extractable) references. Flag ambiguous ones for LLM resolution. Log unresolvable ones.

### 3. Amendment Processing Is a Different Problem Than Initial Ingestion
An amendment document says "In paragraph 12.3, replace X with Y." This requires: (a) understanding amendment document format, (b) locating affected node in existing KG, (c) applying surgical update, (d) preserving old version, (e) validating the result. This is a fundamentally different workflow from processing the base standard.

### 4. "Perfectly Representative" Is Hard to Verify
How do you know the KG perfectly represents the document? This is the validation problem. Proposed multi-pass approach:
- **Structural completeness**: Every paragraph in source has a node in KG. Zero missing, zero duplicated.
- **Hierarchy correctness**: Parent-child relationships match document structure.
- **Content fidelity**: Verbatim text preserved (sampling-based verification).
- **Cross-reference resolution rate**: What % of references were resolved to valid targets?
- **Functional tests**: Can an agent answer known questions correctly using only the KG?

### 5. The Engineering Agent's Cold Start
The first corpus is the hardest. The agent has no patterns, no experience, no SKILL.md files for specific document types. This means V1 must work with heavy LLM reasoning (expensive, slow) and the system gets faster as agents accumulate skills.

---

## Recommended Approach: Build Order

### Phase 0: Foundation (Weeks 1-2)
- Set up agent infrastructure (OpenClaw-style YAML + SKILL.md pattern)
- Integrate Docling for document parsing
- Integrate PageIndex for tree generation
- Set up graph storage (Neo4j or similar)
- Define core KG schema (nodes = structural elements, edges = relationships, bi-temporal metadata)

### Phase 1: Single Document Pipeline (Weeks 3-6)
- Build Corpus Profiler agent (examines FRS 102, discovers patterns)
- Build Pipeline Generator agent (takes profile, generates extraction code)
- Build extraction pipeline for FRS 102 specifically
- Build validation framework
- Produce first complete KG of FRS 102

### Phase 2: API Layer (Weeks 7-8)
- Build MCP Server Generator
- Generate FRS 102-specific MCP tools
- Test with a consumer agent doing basic regulatory queries
- Validate: can agent answer FRS 102 questions using only MCP tools?

### Phase 3: Corpus Evolution (Weeks 9-10)
- Build amendment processing capability
- Handle temporal versioning
- Test with real FRS 102 amendment history

### Phase 4: Multi-Corpus (Weeks 11-12)
- Onboard FRS 105 (simpler, builds confidence)
- Implement cross-corpus edges
- Test cross-corpus queries

### Phase 5: Agent Learning (Weeks 13+)
- Integrate memory system for engineering agents
- Capture patterns from FRS 102/105 onboarding
- Test on Companies Act 2006 (different document type) — does agent generalise?

---

## Key Open-Source Repos to Study

| Repo | Why | URL |
|------|-----|-----|
| PageIndex | Tree index generation, retrieval model | github.com/VectifyAI/PageIndex |
| PageIndex MCP | How to expose document structure as MCP tools | github.com/VectifyAI/pageindex-mcp |
| Docling | Document parsing, DocTags, hierarchy extraction | github.com/docling-project/docling |
| Docling-Graph | How IBM bridges Docling → knowledge graph | github.com/IBM/docling-graph |
| Graphiti/Zep | Temporal knowledge graph architecture | github.com/getzep/graphiti |
| Supermemory | Agent memory system | github.com/supermemoryai/supermemory |
| OpenClaw | Agent architecture pattern (YAML + SKILL.md + computer access) | openclaw.ai |
| mcp-agent | MCP-native agent patterns | github.com/lastmile-ai/mcp-agent |
| KARMA | Multi-agent KG enrichment pipeline | arxiv 2502.06472 |
| SAT-Graph RAG | Ontology-driven temporal legal KG (paper) | arxiv 2505.00039 |

---

## Bottom Line

**Nobody has built what we're building.** The pieces exist — good parsers, good graph databases, good agent frameworks, good memory systems, and excellent academic papers describing what the output should look like. But nobody has assembled them into an autonomous system where AI agents take arbitrary document corpora and produce perfectly representative, temporally-versioned, cross-referenced knowledge graphs with auto-generated APIs.

The closest things are:
- **SAT-Graph RAG** has the right output model but is entirely manual
- **PageIndex** has the right retrieval philosophy but is single-document, no KG
- **Docling-Graph** has the right pipeline direction but requires manual schema definition
- **KARMA** has the right multi-agent architecture but is entity-extraction, not structure-preservation
- **OpenClaw** has the right agent paradigm but is general-purpose, not document-specialised

The gap is clear. The opportunity is to build the bridge between academic vision (SAT-Graph RAG's temporal ontology) and production reality (Docling's parsing + PageIndex's retrieval + OpenClaw's agent pattern + MCP's API standard). The hard parts we must build ourselves are: the corpus profiler, the pipeline generator, the cross-reference resolver, the temporal version manager, and the agent learning loop.


---
  Starting From First Principles

  The Problem Statement (Distilled)

  Take any authoritative document corpus → produce a perfectly representative structured
  backend + clean APIs → so any AI agent can reason over it like a human expert.

  The key words are "perfectly representative." The output must be a faithful structural
  representation of the documents themselves — not entities extracted from them. This is
  a fundamentally different problem from what every existing KG system solves.

  What Was Wrong With The Previous Scaffold

  I jumped straight to infrastructure (agent YAML files, skill loaders, 5 separate agent
  definitions) without first understanding:

  1. What does the output actually look like? — We never tested the KG schema against a
  real document
  2. What does Docling actually produce? — We never parsed a real PDF to see what we're
  working with
  3. What does the agent actually need to do? — We built a loader for agents that don't
  exist yet
  4. Why build a custom agent runtime? — The Claude Agent SDK already provides everything
   we scaffolded (and more)

  The scaffold was ceremony without substance — a multi-agent framework with zero domain
  logic.

  ---
  Three Real Options

  Option A: "Schema-First" — Prove the ontology against real data, then automate

  Start by manually processing ONE document (FRS 102). Parse it with Docling. Inspect the
   actual output. Design the KG schema by hand against real data, informed by SAT-Graph 
  RAG's ontology (Work vs Expression, legislative events, bi-temporal versioning). Build
  the graph manually. Write MCP tools manually. Prove the whole concept works end-to-end.
   THEN automate each step.

  Column 1: Start with
  Column 2: A real PDF, Docling parsing, manual graph design
  ────────────────────────────────────────
  Column 1: Core artifact
  Column 2: The KG ontology — tested against real documents
  ────────────────────────────────────────
  Column 1: Agents come
  Column 2: Later, once we know exactly what they need to do
  ────────────────────────────────────────
  Column 1: Pro
  Column 2: Grounded in reality. No premature abstraction. Schema tested against real
  data
    before building automation.
  ────────────────────────────────────────
  Column 1: Con
  Column 2: Slower start. More manual exploration upfront.

  Option B: "Agent-SDK-Native" — Build domain tools on top of Claude Agent SDK

  The Claude Agent SDK gives us the exact runtime we were trying to build from scratch:
  built-in tools (Read, Write, Edit, Bash, Glob, Grep), subagent orchestration, MCP
  integration, hooks, session persistence, and Docker sandboxing. Instead of writing YAML
   loaders and skill parsers, we build domain-specific MCP tools (Neo4j operations,
  Docling parsing, cross-ref extraction) and let Claude Agent SDK handle orchestration.

  Column 1: Start with
  Column 2: pip install claude-agent-sdk, define agents as AgentDefinition objects
  ────────────────────────────────────────
  Column 1: Core artifact
  Column 2: Domain-specific MCP tools that Claude agents use
  ────────────────────────────────────────
  Column 1: Agents are
  Column 2: Claude Agent SDK query() calls with specialized prompts + tool sets
  ────────────────────────────────────────
  Column 1: Pro
  Column 2: Production agent runtime from day 1. Docker sandboxing solved. Subagents,
    hooks, sessions all built-in. Focus purely on domain logic.
  ────────────────────────────────────────
  Column 1: Con
  Column 2: Tied to Anthropic. Agent loop is a black box. Cost per agent invocation.

  Option C: "Docling-Graph Extension" — Extend IBM's existing pipeline

  Docling-Graph already does document → Pydantic template → knowledge graph → Neo4j.
  Their architecture includes template matching, multi-stage extraction, and graph
  export. Our innovation would be: making template discovery automatic, switching from
  entity-extraction to structure-preservation, adding temporal versioning, and adding MCP
   output.

  Column 1: Start with
  Column 2: Fork/extend docling-graph, study their template system
  ────────────────────────────────────────
  Column 1: Core artifact
  Column 2: Structure-preserving Pydantic templates + auto-discovery
  ────────────────────────────────────────
  Column 1: Agents are
  Column 2: Extensions of Docling-Graph's existing pipeline stages
  ────────────────────────────────────────
  Column 1: Pro
  Column 2: Don't reinvent document→graph pipeline. Production-quality parsing. IBM
    backing.
  ────────────────────────────────────────
  Column 1: Con
  Column 2: Docling-Graph is entity-extraction focused. Structure-preservation requires
    rearchitecting their template model. Their ontology is wrong for our use case.

  ---
  My Recommendation: A + B Combined

  Phase 1 — Schema-First (the smallest solid piece)

  Take ONE real document. Parse it with Docling. Study the output. Design the KG ontology
   by hand, informed by SAT-Graph RAG's model. Build a real graph from a real document.
  Write real MCP tools. Validate: can an agent answer questions about FRS 102 using only
  the KG?

  This gives us the ground truth — a proven schema, a working graph, and a clear
  understanding of what automation needs to do.

  Phase 2 — Agent-SDK-Native (the automation layer)

  Once we know exactly what the profiler/builder/validator agents need to do (because we
  did it manually), build them on Claude Agent SDK. Each agent becomes a query() with
  domain-specific MCP tools. Docker sandboxing comes free. Orchestration comes free. We
  write zero framework code — only domain logic.

  ---
  The Smallest Starting Piece

  The first commit should be:

  1. Parse a real FRS 102 PDF with Docling — see what the actual output looks like
  2. Design the KG ontology against that real output — not in the abstract
  3. Build ONE section of FRS 102 as a graph — manually, in Neo4j
  4. Write ONE MCP tool — get_section(section_number) that retrieves from the graph
  5. Test — can Claude answer a question about FRS 102 using that tool?

  This is a thin vertical slice through the entire system. It proves the concept before
  we automate anything.

  ---
  Which direction do you want to go?

  Sources:
  - Claude Agent SDK Overview
  - Building Agents with Claude Agent SDK
  - Claude Agent SDK Demos
  - Docker Sandboxing for Claude Code
  - SAT-Graph RAG Paper
  - Docling-Graph
  - KARMA Multi-Agent KG Enrichment

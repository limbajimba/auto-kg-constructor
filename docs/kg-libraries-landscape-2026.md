# Knowledge Graph Libraries & Best Practices — 2026 Landscape

## Table of Contents

1. [Python KG Libraries](#1-python-kg-libraries)
2. [Graph Databases](#2-graph-databases)
3. [LLM-Powered KG Construction](#3-llm-powered-kg-construction)
4. [KG Embedding Libraries](#4-kg-embedding-libraries)
5. [KG Validation & Quality](#5-kg-validation--quality)
6. [Best Practices](#6-best-practices-2026)
7. [Rowboat Labs — Case Study](#7-rowboat-labs--case-study)
8. [Selection Matrix](#8-selection-matrix)
9. [Relevance to auto-kg-constructor](#9-relevance-to-auto-kg-constructor)
10. [Sources](#10-sources)

---

## 1. Python KG Libraries

| Library | Description | Best For |
|---------|-------------|----------|
| **NetworkX** | Standard Python graph library. ~15k+ GitHub stars. In-memory, general-purpose. | Prototyping, small-medium graphs, algorithm research |
| **RDFLib** | Standard RDF library. Supports Turtle, JSON-LD, OWL, SPARQL. | Semantic web, W3C-compliant RDF/OWL graphs |
| **kglab** | High-level abstraction over RDFLib, NetworkX, RAPIDS, Pandas. | Integrating RDF with Python data science stack |
| **grape** | High-performance graph library (Rust + Python bindings). | Very large graph analytics and embedding |

---

## 2. Graph Databases

### Neo4j (Community / Enterprise)
- **Type**: Property graph, Cypher query language, ACID-compliant
- **Ecosystem**: Best in class — LangChain, LlamaIndex, GraphRAG SDK integrations
- **Limitation**: JVM-based, degrades under heavy write loads
- **Best for**: Production KGs, general-purpose, excellent tooling/docs

### FalkorDB
- **Successor to**: RedisGraph (EOL Jan 2025)
- **Performance**: Claims 500x faster p99 latency than Neo4j in aggregate expansion benchmarks
- **Key feature**: Ships a GraphRAG SDK for LLM-native KG construction
- **Best for**: High-throughput, latency-sensitive GraphRAG workloads

### Kuzu (Embedded)
- **Type**: Embedded columnar property graph DB, MIT-licensed
- **Usage**: `pip install kuzu` — runs inside your Python process, no server needed
- **Features**: Cypher support, zero-copy bridge to Pandas/PyTorch Geometric/Parquet/Arrow/DuckDB, full-text + vector search
- **Best for**: POC development, embedded analytics, no-server workflows

### Memgraph
- **Type**: Open-source, in-memory C++ graph DB, Neo4j-compatible (Cypher)
- **Performance**: Up to 8x faster than Neo4j on mixed workloads; up to 41x lower latency
- **Best for**: Real-time graph workloads, streaming

### ArangoDB
- **Type**: Multi-model (document + graph + key-value), AQL query language
- **Best for**: Hybrid data models, startups needing flexibility

### TigerGraph
- **Scale**: 73B vertices, 534B edges. Fastest deep-link OLAP queries
- **Best for**: Large-scale enterprise graph analytics

### Amazon Neptune
- **Type**: Fully managed AWS graph DB. Property graphs (openCypher/Gremlin) + RDF (SPARQL)
- **Best for**: AWS-centric organizations

---

## 3. LLM-Powered KG Construction

### Microsoft GraphRAG
- **GitHub**: [microsoft/graphrag](https://github.com/microsoft/graphrag)
- **Approach**: Text → TextUnits → entity/relationship extraction → hierarchical community structure → community summaries
- **Strengths**: Global query mode for cross-corpus reasoning
- **Cost**: ~610K tokens per query (expensive)
- **Best practice**: Fine-tune extraction prompts using built-in Prompt Tuning Guide. Recommends 3-7 node types, 5-15 relationship types.

### LightRAG
- **Released**: October 2024
- **Approach**: Dual-level retrieval (local + global) without community clustering
- **Cost**: ~100 tokens per query vs GraphRAG's 610K. 65-80% cost savings at scale.
- **Performance**: ~30% lower latency than GraphRAG
- **Best for**: Cost-sensitive production deployments

### AutoSchemaKG
- **GitHub**: [HKUST-KnowComp/AutoSchemaKG](https://github.com/HKUST-KnowComp/AutoSchemaKG)
- **Approach**: Fully autonomous — no predefined schema. Simultaneously extracts triples and induces schema from text.
- **Scale**: Built ATLAS KGs: 900M+ nodes, 5.9B edges from 50M documents
- **Quality**: 92% semantic alignment with human-crafted schemas, zero manual intervention
- **Impact**: 12-18 point EM/F1 improvement over BM25 for multi-hop QA
- **Highly relevant** to auto-kg-constructor's autodiscovery philosophy

### Neo4j LLM Knowledge Graph Builder
- **GitHub**: [neo4j-labs/llm-graph-builder](https://github.com/neo4j-labs/llm-graph-builder)
- **Stack**: React + FastAPI, uses LangChain's LLMGraphTransformer
- **Accepts**: PDFs, Office docs, web pages, YouTube transcripts
- **Features**: Chunk-connected-to-document graph, kNN similar chunk graph, entity extraction, community summaries

### LangChain LLMGraphTransformer
- Core of most Neo4j pipelines. `convert_to_graph_documents()` turns LangChain docs into graph documents.
- Highly composable, works with any LLM backend.

### LlamaIndex Property Graph Construction
- Applies `kg_extractors` to each text chunk. Supports schema-free and schema-guided modes.
- Integrates with Neo4j for storage.

### Graphiti (by Zep)
- **GitHub**: [getzep/graphiti](https://github.com/getzep/graphiti)
- **Key innovation**: Real-time, temporally-aware KGs for AI agents
- **Temporal model**: Bi-temporal (event-occurrence time + ingestion time)
- **Updates**: Incremental, no batch recomputation needed
- **Search**: Hybrid — semantic + BM25 + graph traversal with result fusion
- **Performance**: 94.8% accuracy on Deep Memory Retrieval (vs MemGPT's 93.4%), 90% lower latency
- **Best for**: Agent memory, continuously-updated KGs

### FalkorDB GraphRAG SDK
- High-performance path from documents to queryable KGs
- Integrates with OpenAI and LangChain

### FastGraphRAG / MiniRAG
- Lightweight alternatives focused on reducing computation cost further than LightRAG

---

## 4. KG Embedding Libraries

| Library | Description | Best For |
|---------|-------------|----------|
| **PyKEEN** | Most comprehensive KGE library. 40+ models, Optuna HPO, modular architecture. | Link prediction, triple classification, research |
| **DGL-KE** | Extension of DGL for large-scale KG embeddings. GPU-accelerated. | Production-scale embeddings |
| **LibKGE** | Research-focused, emphasis on reproducibility. | Academic experiments |
| **Pykg2vec** | 25 KGE algorithms in PyTorch, Bayesian HPO. | Quick experimentation |
| **PyTorch Geometric (PyG)** | Leading GNN library. 40+ GNN methods, Kuzu/DGL bridges. | GNN-based graph learning |

---

## 5. KG Validation & Quality

| Tool | Description |
|------|-------------|
| **SHACL** | W3C standard for RDF graph validation. 2025 research mapped 69 data quality metrics to SHACL shapes. Tools: `pySHACL` (Python), `rudof` (Rust). |
| **ShEx** | Alternative to SHACL. Triple-expression based. |
| **SHACTOR** | Tool for improving quality of large-scale KGs using validating shapes. |

---

## 6. Best Practices (2026)

### Schema Design
- **3-7 node types, 5-15 relationship types**: GraphRAG's empirical finding — too many reduces extraction accuracy, too few loses distinctions
- **Hybrid ontology**: Start with domain expert review of public ontologies (FOAF, schema.org), extend with LLM-assisted schema induction
- **Discovered types as data**: AutoSchemaKG proves zero-manual-schema achieves 92% alignment. Store types as graph data, not code constants.
- **80/20 rule**: Nail core entity types and relationships first, defer edge cases

### Document-to-KG Pipeline
1. **Profiling phase first** — Sample document, ask LLM open-ended structural questions before committing to extraction schema
2. **Chunk-aware construction** — Store chunks as graph nodes connected to documents (Neo4j LLM KG Builder pattern). Enables hybrid chunk + graph retrieval.
3. **Two-phase extraction** — Outline/structure first, then per-section detail. Necessary due to LLM output token limits.
4. **Verification loop** — Cross-check LLM-extracted claims against source document. PageIndex and AutoSchemaKG both do this.
5. **Prompt tuning** — Sample 1% of corpus to generate domain-adapted prompts (GraphRAG auto-tuning pattern)
6. **Incremental updates** — Prefer architectures that add new documents without full recomputation (LightRAG, Graphiti)

### Temporal & Agent-Oriented KGs
- Graphiti/Zep's **bi-temporal model** (event time + ingestion time) is the emerging standard for agent memory KGs
- The **agentic pattern** (tool call + feedback loop) outperforms one-shot batch extraction for completeness

### Embedded vs Server DBs for POC
- **Kuzu** for POC: no server, MIT license, Cypher-compatible, native Python, Pandas/PyG integration
- **Neo4j** for production: mature ecosystem, Cypher, extensive tooling

---

## 7. Rowboat Labs — Case Study

### Company
- **YC S24** (Summer 2024), founded by Arjun Maheswaran & Ramnique Singh
- Two products: **Rowboat X** (desktop AI coworker with KG) and **Rowboat IDE** (multi-agent builder)
- GitHub: [rowboatlabs/rowboat](https://github.com/rowboatlabs/rowboat)

### How Rowboat X Builds Its Knowledge Graph

#### Storage: Obsidian-style Markdown Vault
The KG is **not a graph database** — it's a folder of plain Markdown files with `[[wiki-links]]` at `~/.rowboat/knowledge/`:

```
knowledge/
  People/           ← One .md per person
  Organizations/    ← One .md per company
  Projects/         ← One .md per initiative
  Topics/           ← One .md per theme
  Voice Memos/      ← Transcripts by date
```

#### Node Templates
Each entity follows a typed Markdown template:

```markdown
# {Full Name}

## Info
**Role:** ...
**Organization:** [[Organizations/Acme Corp]]
**Email:** ...
**Aliases:** comma-separated
**First met:** YYYY-MM-DD

## Summary
2-3 sentences

## Connected to
- [[Organizations/Acme Corp]] — works at
- [[People/David Kim]] — colleague

## Activity
- **2026-01-15** (meeting): Discussed [[Projects/Acme Integration]]

## Key facts
...

## Open items
- [ ] Send API docs — by Friday
```

#### Edge Representation
Relationships are `[[Folder/Name]]` inline links. The system enforces **bidirectional consistency** — if A links to B, B must link back to A.

#### Construction Pipeline

1. **Data sync** (every 5-30 min): Gmail, Google Calendar, Fireflies, Granola → `.md` files
2. **Change detection** (`graph_state.ts`): Hybrid mtime + SHA-256 hash tracking. Only new/changed files proceed.
3. **Agent-driven graph building** (`build_graph.ts`):
   - Builds a `KnowledgeIndex` (in-memory scan of all existing notes) before each batch
   - Formats index as Markdown table, prepends to agent prompt
   - Creates a `note_creation` agent run (Claude SDK) with up to **10 source files per batch**
   - Agent uses workspace tools (`writeFile`, `readFile`, `edit`, `grep`, `glob`) to read/write notes
   - Runs every 30 seconds

#### Note Creation Agent (10-Step Pipeline)

| Step | Action |
|------|--------|
| 0 | Classify source (meeting / email / voice memo) |
| 1 | Filter: skip newsletters, cold outreach, automated mail |
| 2 | Extract all name variants (aliases, emails, roles) |
| 3 | Look up existing notes in pre-built index |
| 4 | Resolve variants to canonical names (entity resolution) |
| 5 | Decide which new entities warrant notes |
| 6 | Extract decisions, commitments, key facts, open items |
| 7 | Detect state changes (project status, role changes) |
| 8 | Dedup and check conflicts with existing notes |
| 9 | Write updates — one file at a time, sequentially |
| 10 | Enforce bidirectional `[[Folder/Name]]` links |

Three **strictness levels** (Low/Medium/High) control how aggressively emails create notes. Auto-configured based on email volume (>100 senders → High, 50-100 → Medium, <30 → Low).

### Rowboat IDE (Multi-Agent Builder)

Separate product — a visual IDE for constructing multi-agent AI systems with a copilot ("Skipper"). Supports:
- **Agent types**: Conversation, Pipeline, Post-process, Escalation
- **Tools**: Builtin workspace tools, MCP servers, Composio OAuth integrations
- **RAG pipeline**: Gemini PDF parsing → vector embedding → Qdrant storage → retrieval

#### Tech Stack

| Layer | Desktop App | Web App |
|-------|-------------|---------|
| UI | Electron + React 19 + Tailwind | Next.js 15 + RSC |
| LLM | Vercel AI SDK (multi-provider) | OpenAI, Anthropic, Google, Ollama |
| Vector store | — | Qdrant |
| Document DB | — | MongoDB |
| Job queue | — | Redis |
| Integration | MCP | MCP + Composio |
| Language | TypeScript (97%) | TypeScript |

---

## 8. Selection Matrix

| System | Cost | Query Type | Update Cost | Best For |
|--------|------|------------|-------------|----------|
| Microsoft GraphRAG | Very High | Global/community | Very High | Complex cross-doc reasoning |
| LightRAG | Low | Local + global | Low | Cost-sensitive production |
| Neo4j LLM Builder | Medium | Hybrid | Medium | General document corpora |
| FalkorDB GraphRAG SDK | Low | Graph-native | Low | High-throughput RAG |
| Graphiti (Zep) | Low | Agent memory | Very Low (incremental) | Agentic / temporal |
| AutoSchemaKG | Medium | Multi-hop QA | Medium | Schema-free large corpora |
| Rowboat X | Low | Navigable vault | Very Low (incremental) | Personal/team KG |

---

## 9. Relevance to auto-kg-constructor

| Pattern | Rowboat | auto-kg-constructor |
|---------|---------|---------------------|
| Storage | Plain Markdown + backlinks | Neo4j / structured graph |
| Node types | 4 hard-coded folders | Autodiscovered from document |
| Edge types | Inline `[[]]` links | Named structural relationships |
| Schema | Fixed Markdown templates | Dynamic — discovered per corpus |
| Construction | Agent tool loop (Claude SDK) | Agent tool loop (planned) |
| Entity resolution | Pre-built index per batch | Cross-reference detection |
| Change tracking | mtime + SHA-256 | SHA-256 cache in `proof/parser/` |
| Batching | 10 files per agent run | Section-by-section parsing |
| Verification | None | `02_inspect.py` + validator agent |

### Key Takeaways

1. **Rowboat validates the agent-driven graph building pattern** — their `note_creation` agent using tool calls to build the graph incrementally is exactly the OpenClaw pattern described in CLAUDE.md.

2. **Rowboat builds entity graphs, we build structural graphs** — fundamentally different KG philosophies. Rowboat extracts people/orgs/topics (traditional NER→KG). We treat document structure itself as the graph (sections, paragraphs, cross-references).

3. **Pre-built index for entity resolution** — Rowboat builds a full in-memory index before each batch and passes it to the agent. This is directly applicable: the `kg-builder` agent should receive a current graph index before creating new nodes/edges.

4. **Gemini for PDF parsing** — Both projects chose Gemini 2.5 Pro for PDF-to-structured-text, validating the technology choice.

5. **AutoSchemaKG is the closest academic validation** — 92% schema alignment with zero predefined types proves the autodiscovery approach at scale.

6. **Kuzu for POC, Neo4j for production** — Consider Kuzu as an embedded alternative during the proof phase to reduce infrastructure friction.

7. **Graphiti's bi-temporal model** aligns with SAT-Graph RAG's Work vs Expression temporal design in our architecture.

---

## 10. Sources

- [NetworkX](https://networkx.org/)
- [RDFLib](https://rdflib.readthedocs.io/)
- [kglab](https://pypi.org/project/kglab/)
- [Neo4j](https://neo4j.com/)
- [FalkorDB](https://www.falkordb.com/) — [FalkorDB vs Neo4j](https://www.falkordb.com/blog/falkordb-vs-neo4j-for-ai-applications/)
- [Kuzu](https://github.com/kuzudb/kuzu) — [Docs](https://docs.kuzudb.com/)
- [Memgraph](https://memgraph.com/) — [Python packages for KGs](https://memgraph.com/blog/best-python-packages-tools-for-knowledge-graphs)
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — [Docs](https://microsoft.github.io/graphrag/)
- [LightRAG overview](https://www.analyticsvidhya.com/blog/2025/01/lightrag/)
- [AutoSchemaKG](https://github.com/HKUST-KnowComp/AutoSchemaKG) — [Paper](https://arxiv.org/abs/2505.23628)
- [Neo4j LLM Graph Builder](https://github.com/neo4j-labs/llm-graph-builder)
- [Graphiti / Zep](https://github.com/getzep/graphiti) — [Paper](https://arxiv.org/abs/2501.13956)
- [PyKEEN](https://github.com/pykeen/pykeen)
- [PyTorch Geometric](https://github.com/pyg-team/pytorch_geometric)
- [Rowboat Labs](https://www.rowboatlabs.com/) — [GitHub](https://github.com/rowboatlabs/rowboat)
- [Rowboat on YC](https://www.ycombinator.com/companies/rowboat-labs)
- [Rowboat HN Launch](https://news.ycombinator.com/item?id=46962641)
- [Awesome-GraphRAG](https://github.com/DEEP-PolyU/Awesome-GraphRAG)
- [SHACL data quality (2025)](https://arxiv.org/abs/2507.22305)
- [LLM-empowered KG construction survey](https://arxiv.org/abs/2510.20345)

# Knowledge Graphs: A Reality Check

An honest assessment of what KGs are, what you can do with them, the tools
that exist for interacting with them, the downsides, and whether the
auto-kg-constructor problem is worth solving.

---

## Table of Contents

1. [What Can You Actually Build on a KG?](#1-what-can-you-actually-build-on-a-kg)
2. [Tools for Interacting with Built KGs](#2-tools-for-interacting-with-built-kgs)
3. [The Real Downsides](#3-the-real-downsides)
4. [The "So What" Problem](#4-the-so-what-problem)
5. [KGs in the LLM Era](#5-kgs-in-the-llm-era)
6. [Document-Structural KGs: Tree vs Graph vs Vector](#6-document-structural-kgs-tree-vs-graph-vs-vector)
7. [The Honest Verdict for auto-kg-constructor](#7-the-honest-verdict-for-auto-kg-constructor)

---

## 1. What Can You Actually Build on a KG?

### Proven, Shipped Products

| Company | What the KG Enables | Could This Work Without a KG? |
|---------|---------------------|-------------------------------|
| **Google** (Knowledge Graph, 2012) | Knowledge Panels, "People also search for", disambiguation, answer boxes. 500B+ facts, 5B+ entities. | No. Multi-hop entity disambiguation requires traversal. |
| **LinkedIn** (Economic Graph) | 2nd-degree connection discovery, job recommendations, skills gap analysis, labor market reports. 590M members, 30M companies. | No. The product IS the graph. |
| **Amazon** (AutoKnow) | Semantic product search ("USB-C cable for MacBook"), attribute augmentation, "frequently bought together". 200% increase in product facts. | Partially. But cross-category attribute inference needs graph traversal. |
| **Airbnb** | Search, discovery, Trip Planner. Graph connects listings, neighborhoods, amenities, reviews, hosts. | Partially. But neighborhood-level reasoning is a traversal problem. |
| **Uber** (Databook) | Internal data lineage. "Who owns this dataset? What depends on it? Why did this ML feature change?" | Yes, with a lot of SQL joins. Graph makes it 10x easier. |
| **Fraud detection** (PayPal, banks) | Detect fraud rings — accounts sharing phone/address/device that look innocent individually but are obviously connected as a network. | Very hard in SQL (recursive CTEs become unmaintainable). Graph is the right model. |
| **Drug discovery** (AstraZeneca, Bayer) | Find non-obvious gene → protein → pathway → drug relationships across biomedical literature. | Not at scale. Multi-hop reasoning over heterogeneous biomedical data is a graph problem. |
| **MITRE ATT&CK** | Map observed attacker behavior to known tactics/techniques/procedures. | Possible but the graph IS the knowledge model here. |

### The Pattern Across All Successes

KGs deliver value when:
- The domain has **rich, interconnected relationships** (not just attributes)
- There is a **traversal problem**: "what is reachable from X?"
- **Multi-hop reasoning** is required (answer not in one record, needs 2-4 joins)
- **Completeness matters** (find ALL instances, not just similar ones)
- Data has **heterogeneous types** that resist a single SQL schema

---

## 2. Tools for Interacting with Built KGs

### Query Languages

| Language | Model | Best For | Portability |
|----------|-------|----------|-------------|
| **Cypher / GQL** | Property Graph | General-purpose, analytics, pattern matching | High (ISO GQL standard, 2023) |
| **SPARQL** | RDF Triples | Semantic web, ontologies, federated queries | High (W3C standard) |
| **Gremlin** | Property Graph | Multi-vendor, imperative traversals | High (TinkerPop) |
| **AQL** | Multi-model | ArangoDB mixed workloads | None (ArangoDB only) |

**Cypher** is the dominant choice for property graphs. ASCII-art pattern matching
(`(a)-[:CITES]->(b)`) is intuitive. Neo4j 5.x Quantified Path Patterns enable
variable-length traversals with pruning. GQL (ISO 39075) formalizes this as
the SQL-of-graphs.

**SPARQL** is verbose and steep learning curve but is the only option for
RDF/ontological data. Every academic KG (Wikidata, DBpedia, UniProt) exposes
a SPARQL endpoint.

### Search on KGs

| Type | Tool | How It Works |
|------|------|--------------|
| **Full-text** | Neo4j fulltext index (Lucene) | `CALL db.index.fulltext.queryNodes(...)`. Fuzzy, wildcard, phrase, boolean. |
| **Vector (semantic)** | Neo4j 5.11+ vector index | `CREATE VECTOR INDEX` + `db.index.vector.queryNodes(...)`. Any embedding model. |
| **Hybrid: Vector + Graph** | `neo4j-graphrag-python` library | 4 retrievers: `VectorRetriever`, `VectorCypherRetriever`, `HybridRetriever`, `HybridCypherRetriever` |
| **NL → Cypher** | Text2Cypher (LangChain, LlamaIndex, Neo4j) | LLM translates natural language to Cypher, executes, answers. |

**The hybrid pattern is the current best practice**: semantic search to find an
entry point, then deterministic graph traversal from there. Graphiti (Zep)
achieves P95 300ms retrieval using BM25 + vector + graph traversal with no LLM
at retrieval time.

### Traversal & Pathfinding (Neo4j GDS)

65+ production-ready algorithms:

- **Shortest path**: Dijkstra, A*, Delta-Stepping
- **K-shortest paths**: Yen's algorithm (top-k distinct paths)
- **BFS/DFS**: with early termination
- **Random Walk**: for node2vec embeddings
- **Minimum Spanning Tree**

### Graph Analytics (Neo4j GDS)

| Category | Algorithms |
|----------|-----------|
| **Community detection** | Louvain, Leiden, Label Propagation, K-Core, WCC/SCC |
| **Centrality** | PageRank, Betweenness, Closeness, Eigenvector, HITS |
| **Similarity** | Node Similarity (Jaccard), KNN in embedding space |
| **Link prediction** | Common neighbors, Adamic-Adar, logistic regression pipeline |

### Visualization

| Tool | Best For | Scale |
|------|----------|-------|
| **Neo4j Browser** | Dev/debugging, Cypher REPL | Hundreds of nodes |
| **Neo4j Bloom** | Business users, NL search, no Cypher needed | Medium graphs |
| **Gephi** (v0.10, 2025) | Publication-quality diagrams, Vulkan GPU renderer | 10M+ edges |
| **Graphistry** | GPU-accelerated investigation, ML-assisted pivots | Billions of edges |
| **GraphXR** (Kineviz) | 3D immersive exploration | Medium-large |
| **Linkurious** | Fraud/cybersecurity investigation | Enterprise |
| **KeyLines** | Embed graph viz in custom apps (JS SDK) | Custom |

### API Layers

| Approach | Tool | Description |
|----------|------|-------------|
| **GraphQL** | Neo4j GraphQL Library | Auto-generates full GraphQL schema from Neo4j. Nested traversals become nested queries. |
| **REST** | Neo4j HTTP/Bolt API | `POST /db/neo4j/tx/commit` with Cypher JSON body. Official drivers for Python, Java, JS, Go, .NET, Rust. |
| **MCP** | `neo4j-contrib/mcp-neo4j` | 3 MCP servers: Cypher execution, agent memory, data modeling. LLM calls `read_neo4j_cypher` tool. |
| **MCP** | Graphiti MCP Server | Temporal KG as MCP tools for agent memory. |
| **Query engine** | PuppyGraph | Graph query layer over existing data lakes (Iceberg, Postgres, DuckDB). No ETL. |

### Agent Frameworks for KGs

| Framework | Key Component | What It Does |
|-----------|--------------|--------------|
| **LangChain** | `GraphCypherQAChain` | NL → schema-injected prompt → LLM generates Cypher → executes → LLM answers |
| **LangChain** | `Neo4jVector` | Vector index retrieval via LangChain retriever interface |
| **LlamaIndex** | `PropertyGraphIndex` | Multi-backend (Neo4j, NebulaGraph, in-memory). `SchemaLLMPathExtractor` for construction. |
| **LlamaIndex** | `KnowledgeGraphRAGRetriever` | Hybrid: keyword entity extraction → graph traversal → embedding similarity |
| **neo4j-graphrag-python** | `VectorCypherRetriever` | Vector search → Cypher traversal from hits. Most relevant for this project. |
| **Graphiti** (Zep) | Temporal agent memory | Bi-temporal KG, incremental updates, P95 300ms, MCP server |

### Reasoning

| Type | Tools | Maturity |
|------|-------|----------|
| **OWL reasoning** | HermiT, ELK, Pellet (Stardog), Jena rules | Production for semantic web. Not relevant for property graphs. |
| **SHACL validation** | pySHACL, rudof (Rust), Jena SHACL | Production for RDF. Concept useful for property graph constraints. |
| **KG embeddings** | PyKEEN (40+ models), DGL-KE, LibKGE | Research → production. Link prediction, discovering implicit edges. |
| **Neurosymbolic** | OWL + neural models | Academic. No production tooling yet. |

---

## 3. The Real Downsides

### Construction Cost

| Era | Cost | Time |
|-----|------|------|
| Pre-LLM (manual) | Ontology engineer + NLP pipeline + manual curation | Months |
| LLM-powered (2024+) | API costs + verification | Days-weeks |
| Microsoft GraphRAG | ~$7 to index a 32K-word book. Millions of API calls at scale. | Hours |

LLMs lower construction cost dramatically but introduce hallucinated
relationships, inconsistent entity boundaries, and verification overhead.

### Maintenance: The Staleness Problem (The #1 Killer)

A KG is a snapshot. It diverges from reality the moment you build it.

- **73% of enterprise RAG deployments (many with KG components) fail within
  the first year**, with knowledge staleness as a primary culprit
- Schema drift: adding types is easy; renaming/deprecating requires cascading
  changes to all queries, apps, and docs
- One documented case: 40% cost-per-query increase due to monthly retraining
  pipelines that were planned as quarterly
- Organizations that invest 6-12 months building a KG find 18 months later
  the data quality has degraded to where downstream systems produce wrong
  answers

**For static document corpora** (a specific version of FRS 102) this is
manageable. For anything reflecting a changing world, it's the primary risk.

### Query Complexity

- Simple Cypher: learnable in a weekend
- Complex multi-hop traversals with conditional logic: genuinely hard
- SPARQL: steep learning curve, fragmented ecosystem
- Text-to-Cypher with LLMs: significant error rates on complex patterns
- Non-technical users cannot query directly — you always need an application
  layer

### Scale

- Neo4j Community Edition: no sharding, entire graph on one server
- Fine for single-document POC, hard constraint for multi-org corpora
- Enterprise Neo4j clustering is expensive
- FalkorDB claims sub-50ms at scale but is newer/less battle-tested

### The "20% Problem"

Building the initial graph is **not the hard part**. The hard parts:

1. **Entity resolution**: do two mentions of "Section 11.14" in different
   documents merge or stay separate?
2. **Provenance tracking**: where did each triple come from?
3. **Access control**: different users see different subsets
4. **The application layer**: the graph delivers zero value without UIs/APIs
   built on it
5. **Governance**: who owns the ontology? Who approves schema changes? This
   is a political problem, not a technical one.

### When KGs Are Worse Than Simpler Alternatives

| Problem | Better Tool |
|---------|------------|
| Semantic similarity search | Vector store |
| Tabular data with simple relationships | SQL with proper indexes |
| Ad-hoc analytics over large datasets | Columnar (DuckDB/Parquet) |
| Team has zero graph expertise | SQL + self-joins |
| Source data changes frequently with no update pipeline | Don't build a KG |
| Queries are always node lookups, never traversals | JSON document store |

**The brutal practitioner take**: most problems people think need a graph can
be solved with Postgres and a self-join. The graph becomes necessary when you
have >3 hops of traversal, heterogeneous relationship types, or evolving
schema.

---

## 4. The "So What" Problem

This is the most common KG failure mode:

1. Data team builds technically impressive KG
2. It sits behind a Cypher/SPARQL endpoint only the builders can query
3. Intended end users have no interface to it
4. The "application layer" was never built
5. KG is abandoned within 12-18 months

**Root cause**: treating the KG as an IT project rather than a product. The
graph has no users until you build user-facing features on top. **A KG is
infrastructure, not a product.**

Documented failure patterns:
- Recruiting ontology abandoned after 6 months: costs scaled faster than
  returns, couldn't validate assumptions
- Political failures: leadership interest died before the application layer
  was built
- "The entropy wall": "Good efforts by really smart people with plenty of
  resources hit an entropy wall before too long, and the approach is eventually
  abandoned. There are literally hundreds of examples."

---

## 5. KGs in the LLM Era

### Arguments That LLMs Replace KGs

- LLMs internalized structured knowledge during training
- For general-knowledge questions, you don't need a graph
- LLMs + vector search covers 80% of what KGs were used for, at lower cost
- Freebase was deprecated (2016) partly because neural search internalized it

### Arguments That LLMs Make KGs More Valuable (Stronger for Our Case)

1. **Private/specialized corpora**: LLMs haven't seen your internal documents.
   FRS 102's specific cross-references and amendment history are unreliable in
   parametric knowledge. A KG built from the actual document is authoritative.

2. **Hallucination grounding**: ICLR 2025 research showed 26.5% improvement
   in factual accuracy when grounding LLM reasoning in KGs vs ungrounded.

3. **LLMs lower construction cost**: LLMs *building* KGs (our approach), not
   competing with them. AutoSchemaKG: 95% alignment with zero predefined types.

4. **Deterministic retrieval**: For compliance/legal, "find all references to
   Section 11.14" must be complete and exact. Vector similarity will miss edge
   cases. Graph traversal is deterministic.

5. **Multi-hop reasoning**: GraphRAG shows 6.57% accuracy and 27.94% recall
   improvement over vanilla RAG on multi-hop questions.

### The Synthesis

KGs are **not becoming obsolete** but are **becoming more specialized**:

**KG wins**: Private corpora, multi-hop traversal, completeness-requiring
retrieval, provenance/explainability, stable corpora where construction cost
amortizes.

**LLM + vector wins**: General knowledge Q&A, simple entity lookup, fuzzy
semantic retrieval.

**The trend**: lightweight graph structures combined with vector retrieval
(LazyGraphRAG reduced indexing cost to 0.1% of full GraphRAG while retaining
most quality).

---

## 6. Document-Structural KGs: Tree vs Graph vs Vector

This is the question most directly relevant to auto-kg-constructor.

### What a Tree Gives You (PageIndex Approach)

PageIndex achieves **98.7% accuracy** on FinanceBench with pure tree-search
over document hierarchy. No vectors, no graph DB. A tree:

- Handles "find all info about Section 11" correctly and exhaustively
- Supports incremental updates (re-index only affected subtree)
- Requires no graph database infrastructure
- Produces deterministic, auditable results

**A tree is sufficient for**: single-document retrieval, section-to-content
lookups, hierarchical navigation, "what does section X say?" queries.

### What a Graph Adds Over a Tree

| Relationship Type | Tree Can Represent? | Example |
|-------------------|---------------------|---------|
| Parent-child hierarchy | Yes | Section 11 → Section 11.14 |
| Cross-references | **No** | "Section 11.14 shall be read in conjunction with Section 12.3" |
| Defined term networks | **No** | "Amortised cost" defined in Glossary, used in 23 sections, modified by 3 amendments |
| Amendment/version edges | **No** | Original text ↔ 2017 amendment (temporal edges) |
| External references | **No** | "See IAS 32 paragraph 11" (cross-document) |
| Definitional dependency chains | **No** | "Financial instrument" → "contractual obligation" → "party" |

### When the Graph Advantage Actually Matters

**Graph wins for**:
- "List all sections that reference Section 11.14" (impossible with tree)
- "What terms are defined in the glossary and where are they used?"
- "Trace all paragraphs affected by the 2017 amendment"
- "What cross-standard references exist between FRS 102 and IAS 39?"
- "Find all paragraphs using 'amortised cost' that could be affected by a
  definition change" (reverse traversal)

**Tree is sufficient for**:
- "What does Section 11.14 say?" (direct lookup)
- "List all sections in chapter 11" (hierarchy traversal)

**Vector search is better for**:
- "Find sections conceptually similar to this excerpt" (semantic similarity)
- "Find all places hedge accounting is discussed, even unlabeled" (fuzzy)

### The Risk

Building full graph infrastructure for what amounts to **"a tree with a
cross-reference index"** may be over-engineering. The tree gives you structure
for free; cross-references are the marginal value. A pragmatic middle ground:
tree + explicit cross-reference list stored as simple edges, possibly without
a full graph database.

---

## 7. The Honest Verdict for auto-kg-constructor

### Is the Problem Worth Solving?

**Yes, but the value is narrower than it first appears.**

The real value proposition is not "build a KG from documents" — that is the
cost center. The value is **"let an AI agent navigate a regulatory corpus with
the precision of a human expert"**. Specifically:

- Deterministic cross-reference traversal (not possible with RAG alone)
- Complete term resolution across a multi-document corpus
- Auditable provenance (which paragraph, which version, which amendment)
- Multi-hop reasoning over document structure

These are genuine needs in compliance, legal, and technical documentation
domains. They are NOT well-served by vector search or LLM parametric knowledge.

### What Happens After Autodiscovery?

This is the key "so what" question. If you solve autodiscovery perfectly, you
still need:

1. **The query layer** — MCP server exposing Cypher tools to Claude agents.
   `neo4j-contrib/mcp-neo4j` already exists. This is the bridge from graph to
   agent.

2. **The retrieval pattern** — Hybrid search: vector/BM25 to find entry
   points, then deterministic graph traversal. `neo4j-graphrag-python`
   `VectorCypherRetriever` implements this.

3. **An actual use case** — "agent answers compliance questions about FRS 102"
   is concrete. "agent builds a KG" is not a use case; it is a capability.

4. **The feedback loop** — Agent queries graph → finds gap → triggers
   extraction for missing sections → retries. This is the OpenClaw pattern and
   is the core differentiator.

### The Risk to Manage

The #1 risk is **building infrastructure nobody uses**. The mitigation:

- **Prove the query layer first**: build one end-to-end query ("what sections
  are affected by a change to the definition of 'amortised cost'?") and show
  it works with the graph but not without it. This is your proof of value.
- **Keep construction as cheap as possible**: Gemini API + SHA-256 caching is
  right. Don't build a complex pipeline before proving the query side.
- **The MCP server is the product, not the graph**: the graph is internal
  infrastructure. The MCP server is what agents interact with. Build toward
  that.

### Decision Framework

| Question | If Yes → | If No → |
|----------|----------|---------|
| Do queries require cross-reference traversal? | Graph | Tree + JSON |
| Do queries span multiple documents/versions? | Graph | Single-doc index |
| Must retrieval be complete (not best-match)? | Graph | Vector search |
| Is the corpus relatively stable? | Graph (construction cost amortizes) | Consider staleness risk |
| Can you build the application layer? | Graph | Don't build a KG nobody will query |

For FRS 102 and similar regulatory/technical corpora: **yes to all five**.
The graph approach is justified, but only if the query/agent layer gets built
alongside or before the construction pipeline.

---

## Sources

### Products & Industry
- [Industry-scale Knowledge Graphs: Lessons and Challenges — ACM Queue](https://queue.acm.org/detail.cfm?id=3332266)
- [Building product graphs automatically — Amazon Science](https://www.amazon.science/blog/building-product-graphs-automatically)
- [Architecture of Airbnb's Knowledge Graph](https://www.linkedin.com/pulse/architecture-airbnbs-knowledge-graph-arpit-bhayani)
- [Turning Metadata Into Insights with Databook — Uber](https://www.uber.com/blog/metadata-insights-databook/)
- [From the Economic Graph to Economic Insights — LinkedIn](https://www.linkedin.com/blog/engineering/economic-graph/from-the-economic-graph-to-economic-insights-building-the-infra)

### Failures & Downsides
- [Why Most Enterprise Ontologies & Knowledge Graphs Fail Part 2](https://vinvashishta.substack.com/p/why-most-enterprise-ontologies-and-376)
- [Why Graph Implementations Fail — Enterprise Knowledge](https://enterprise-knowledge.com/why-graph-implementations-fail-early-signs-successes/)
- [5 Reasons Knowledge Graph Will Never Bloom](https://dongshengwang.medium.com/5-reasons-knowledge-graph-will-never-bloom-418601957f33)
- [The Silent Failure Loop: RAG Degradation](https://ragaboutit.com/the-silent-failure-loop-why-real-time-knowledge-graphs-are-your-only-defense-against-production-rag-degradation/)

### Tools & Frameworks
- [Neo4j Graph Data Science](https://neo4j.com/product/graph-data-science/)
- [neo4j-graphrag-python](https://github.com/neo4j/neo4j-graphrag-python)
- [neo4j-contrib/mcp-neo4j](https://github.com/neo4j-contrib/mcp-neo4j)
- [Graphiti / Zep](https://github.com/getzep/graphiti) — [Paper](https://arxiv.org/abs/2501.13956)
- [Neo4j GraphQL Library](https://neo4j.com/product/graphql-library/)
- [LangChain Neo4j Integration](https://neo4j.com/labs/genai-ecosystem/langchain/)
- [LlamaIndex PropertyGraphIndex](https://neo4j.com/blog/developer/property-graph-index-llamaindex/)
- [Building KGs with Claude and Neo4j MCP](https://neo4j.com/blog/developer/knowledge-graphs-claude-neo4j-mcp/)

### LLM + KG Research
- [GraphRAG Costs Explained — Microsoft](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/graphrag-costs-explained-what-you-need-to-know/ba-p/4207978)
- [LazyGraphRAG — Microsoft Research](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)
- [RAG vs GraphRAG Systematic Evaluation](https://arxiv.org/html/2502.11371v1)
- [Grounding LLM Reasoning with KGs — ICLR 2025](https://arxiv.org/abs/2502.13247)
- [PageIndex: 98.7% on FinanceBench](https://venturebeat.com/infrastructure/this-tree-search-framework-hits-98-7-on-documents-where-vector-search-fails)
- [You Probably Don't Need GraphRAG](https://medium.com/@amrwrites/you-probably-dont-need-graphrag-0bc9cf671db1)

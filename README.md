# Auto KG Constructor

A multi-agent system that turns a corpus of authoritative documents into a knowledge graph whose nodes are the document's own structural elements (sections, paragraphs, defined terms, tables) rather than entities extracted from the text. Every node and edge carries bi-temporal metadata so the graph can hold multiple versions of a document and track when each fact was true and when it was recorded. The intended output is an MCP server that lets another agent navigate the corpus through corpus-specific tools.

This repository is an early-stage scaffold. The data model, the Neo4j storage layer, and the agent-definition loader are implemented and tested. The parsing, orchestration, and MCP-generation layers are present as module stubs with the design recorded but no working code yet. Read the status section before trying to run a full corpus through it, because that path does not exist yet.

## The idea

Most systems that build knowledge graphs from documents look *through* the document at the world it describes: they extract entities and the relationships between them, then discard the document's structure. That works for general question answering. It does not work for regulatory standards, legislation, or other documents where the structure itself carries meaning. In a document like an accounting standard, "paragraph 12.3" is an address, "see Section 5" is a typed link, a bold sentence may be a mandatory requirement while the plain sentence next to it is only guidance, and an amendment published two years later surgically rewrites one clause without touching the rest.

Auto KG Constructor takes the opposite stance. It looks *at* the document. The graph it builds is meant to be a faithful, addressable, navigable representation of the corpus: the hierarchy becomes parent-child edges, cross-references become typed reference edges, defined terms become nodes linked to the paragraphs that use them, and amendments become events linked to the clauses they change.

The work splits into two layers. This project is Layer A, the construction crew: agents and tools that read a corpus, work out how it is structured, and build the graph plus its API. Layer B is the tenant: whatever consumer agent later reasons over that corpus using the generated API. The scope here is the building, not the occupants.

For the full survey of existing tools, the gaps this project targets, and the architectural reasoning behind the design, see [docs/corpus-kg-landscape-analysis.md](docs/corpus-kg-landscape-analysis.md). For project context and conventions, see [CLAUDE.md](CLAUDE.md).

## How it is meant to work

The design is a five-stage pipeline driven by an orchestrator. Each stage is an agent with a defined input and output.

```
raw documents
    -> [parsing layer]          Docling (PageIndex intended)
parsed documents
    -> corpus-profiler          discovers structural patterns
corpus profile
    -> pipeline-generator       writes deterministic extraction code
extraction pipeline
    -> kg-builder               populates the Neo4j graph
knowledge graph
    -> validator                multi-pass quality check
validation report
    -> mcp-server-generator     if validation passes
MCP server
```

The roles, as defined in the agent files under `agents/`:

- **corpus-profiler**: examines the parsed corpus and discovers how it is structured. It classifies the document type, maps the hierarchy levels, derives regex patterns for the numbering schemes, catalogs cross-reference syntax (internal, external, ambiguous), works out which formatting carries meaning (for example bold as a mandatory requirement), and records glossary and amendment conventions. Its output is a `CorpusProfile`, the blueprint every later stage reads.
- **pipeline-generator**: takes the `CorpusProfile` and writes Python extraction code. This is the "LLM as software engineer" step. The constraint is that the generated code is deterministic and runs without any LLM calls: the profiler uses an LLM to find patterns, the generator uses an LLM to write code, and the code itself is plain regex and tree construction so extraction is reproducible.
- **kg-builder**: runs the generated pipeline against the parsed documents and populates Neo4j. It creates one node per structural element, stores verbatim content and a content hash on leaf nodes, builds the containment and ordering edges, attempts to resolve every cross-reference into a typed edge, and links defined terms to their usages.
- **validator**: checks that the graph faithfully represents the source through several passes: structural completeness (every source paragraph has exactly one node, no duplicates), hierarchy correctness, content fidelity by sampling, cross-reference resolution rate, and functional tests such as reconstructing the table of contents or looking up a defined term.
- **orchestrator**: routes data between the agents, enforces the dependency order, retries failed stages with error context (up to three loops before escalating to a human), and only runs MCP generation once validation passes.

The "temporally-versioned" part of the description maps to the bi-temporal model in the schema. Every node and edge carries `valid_from` and `valid_until` (when the fact is true in the real world) and `recorded_at` (when it entered the graph). The schema also defines node and edge types for amendments and supersession (`AMENDMENT`, `AMENDS`, `SUPERSEDES`, `EFFECTIVE_FROM`), which is how an amendment is meant to be recorded as a first-class event rather than an in-place edit. The agent that performs amendment processing is described in the landscape doc but is not built yet.

## Agent definition format

The agents follow a file-based pattern (described in the codebase as OpenClaw-inspired). Each agent is a directory under `agents/` containing:

- `AGENT.yaml`: identity and configuration. Name, description, role, phase, declared `inputs` and `outputs`, a `depends_on` list that encodes the pipeline order, a model id, and a list of operating constraints.
- `INSTRUCTIONS.md`: the operating manual, a step-by-step description of how the agent does its job.
- `MEMORY.md`: a place for patterns learned across runs. In the committed agents these are empty placeholders. Per the `.gitignore`, runtime-generated memory directories are not committed.
- `skills/`: an optional directory of skill folders, each with a `SKILL.md` that has YAML frontmatter (name, description) and a markdown body. Only `corpus-profiler` ships skills today: `detect-numbering`, `detect-crossrefs`, and `detect-formatting-semantics`.

`src/auto_kg/runtime/agent_loader.py` reads this format. `load_agent` parses one directory into an `AgentDef` dataclass, `load_skill` parses a `SKILL.md` into a `SkillDef`, and `load_all_agents` walks the whole `agents/` tree. This loader is implemented and tested. What is not yet present is the runtime that takes a loaded `AgentDef`, builds a system prompt from its instructions, and drives an LLM through the agent's task. The loader reads the definitions; nothing executes them yet.

## The knowledge graph schema

The schema in `src/auto_kg/core/schema.py` is the most complete part of the repository. It is built on Pydantic v2 and defines:

- **Node types** (`NodeType`): `corpus`, `document`, `version`, `part`, `section`, `subsection`, `paragraph`, `table`, `figure`, `appendix`, `glossary`, `defined_term`, `footnote`, `example`, `amendment`.
- **Edge types** (`EdgeType`): hierarchy (`contains`, `follows`), cross-references (`references`, `references_external`), definitions (`defines`, `uses_term`), temporal and amendment links (`amends`, `supersedes`, `effective_from`), and semantic links (`requires`, `permits`, `constrains`).
- **`BiTemporalMeta`**: the `valid_from` / `valid_until` / `recorded_at` triple attached to every node and edge.
- **`KGNode`**: a deterministic id (for example `frs102:v2022:s12.3`), node type, label, optional verbatim content, a content hash for change detection, hierarchy level, original numbering, a preserved-formatting dictionary, extensible metadata, and the temporal block.
- **`KGEdge`**: source and target ids, edge type, optional label, weight, metadata, and the temporal block.
- **`CorpusProfile`** plus `NumberingScheme`, `CrossRefPattern`, and `FormattingSemantic`: the structured output of the profiler, including the corpus name, document type, hierarchy levels, the discovered numbering and cross-reference patterns, formatting-to-meaning mappings with confidence scores, and glossary and amendment conventions.

## Graph storage

`src/auto_kg/core/graph.py` is an async Neo4j client (`GraphStore`) built on the official `neo4j` async driver. It connects and closes, creates a uniqueness constraint on node id and an index on node type, upserts nodes and edges (flattening the temporal block into top-level properties and labeling each node with its node type), fetches a node by id, and returns a node's direct children ordered by numbering. This is enough to write and read the schema against a running Neo4j; it is not yet wired into any pipeline that produces nodes to store.

## Repository structure

```
auto-kg-constructor/
  agents/                         File-based agent definitions
    orchestrator/                 Pipeline coordinator
      AGENT.yaml, INSTRUCTIONS.md, MEMORY.md
    corpus-profiler/              Structure-pattern discovery
      AGENT.yaml, INSTRUCTIONS.md, MEMORY.md
      skills/
        detect-numbering/SKILL.md
        detect-crossrefs/SKILL.md
        detect-formatting-semantics/SKILL.md
    pipeline-generator/           Generates deterministic extraction code
    kg-builder/                   Populates the Neo4j graph
    validator/                    Multi-pass quality checks
  src/auto_kg/
    __init__.py                   Package version
    core/
      schema.py                   KG schema and CorpusProfile (implemented)
      graph.py                    Async Neo4j GraphStore (implemented)
    runtime/
      agent_loader.py             Loads AGENT.yaml + SKILL.md + memory (implemented)
    parsing/__init__.py           Docling + PageIndex layer (stub, docstring only)
    orchestrator/__init__.py      Multi-agent coordination (stub, docstring only)
    mcp/__init__.py               MCP server generation (stub, docstring only)
  tests/
    test_schema.py                Schema model tests
    test_agent_loader.py          Agent loader and dependency-chain tests
  docs/
    corpus-kg-landscape-analysis.md   Landscape survey, gaps, and build plan
  docker-compose.yml              Neo4j 5 Community with APOC
  pyproject.toml                  Project metadata and dependencies
  .env.example                    Environment variable template
  CLAUDE.md                       Project context and conventions
```

## Tech stack

- Python 3.12 or newer (the `.python-version` pins 3.13), managed with `uv`.
- Pydantic v2 for all data models.
- Neo4j 5 Community Edition for graph storage, run via Docker with the APOC plugin, accessed through the official async `neo4j` driver.
- Declared dependencies for the parts still to be built: `docling` for document parsing, `graphiti-core` for the temporal knowledge graph, the `mcp` SDK for the output API, and `anthropic` for LLM calls. These are listed in `pyproject.toml` but are not yet imported by any code in `src/`. PageIndex is named in the design and docstrings but is not a declared dependency.
- Tooling: pytest with `pytest-asyncio` and `pytest-cov`, Ruff for linting, and mypy in strict mode.

## Getting started

These steps install the package and run the test suite, which is the part that works today.

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker (for Neo4j), and Python 3.12 or newer.

```bash
# Install dependencies, including dev tools
uv sync --extra dev

# Start Neo4j (browser on 7474, Bolt on 7687)
docker compose up -d

# Run the tests
uv run pytest
```

Other commands defined in the project:

```bash
uv sync                    # Install runtime dependencies only
uv run ruff check src/     # Lint
uv run mypy src/           # Type-check (strict)
```

Environment variables: copy `.env.example` to `.env` and fill in the values.

```
ANTHROPIC_API_KEY=...                 # for LLM-driven agents (not yet wired in)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme               # matches docker-compose.yml default
OPENAI_API_KEY=...                    # for graphiti-core if used
```

The Docker Compose file sets the Neo4j password to `changeme`; change it in both places for anything beyond local experimentation.

## Using what exists today

You can build and inspect schema objects, and you can load the agent definitions, without the rest of the pipeline. For example:

```python
from auto_kg.core.schema import KGNode, KGEdge, NodeType, EdgeType

section = KGNode(
    id="frs102:v2022:s12.3",
    node_type=NodeType.SUBSECTION,
    label="Section 12.3 - Basic Financial Instruments",
    content="An entity shall recognise a financial asset or liability...",
    level=3,
    numbering="12.3",
)
edge = KGEdge(
    source_id="frs102:v2022:s12",
    target_id="frs102:v2022:s12.3",
    edge_type=EdgeType.CONTAINS,
)
```

```python
from pathlib import Path
from auto_kg.runtime.agent_loader import load_all_agents

agents = load_all_agents(Path("agents"))
print(sorted(agents))           # the five defined agents
print(agents["corpus-profiler"].skills)   # the three profiler skills
```

The `GraphStore` in `auto_kg.core.graph` can persist these objects to a running Neo4j instance. There is no command-line entry point, no end-to-end "ingest a corpus" command, and no agent execution loop. Those belong to the parts not yet built.

The examples used throughout the code and tests are drawn from UK accounting standards (FRS 102), which is the first target corpus named in the build plan, but nothing in the schema is specific to that domain.

## Status and maturity

This is a scaffold with a clear design, not a working pipeline. As of the current commit history (a single substantive commit on top of an initial commit), the state is:

- Implemented and tested: the structure-preserving bi-temporal schema, the async Neo4j storage layer, and the agent-definition loader. Test coverage exists for the schema models, the loader, and the agent dependency chain.
- Defined as content but not executed: the five agents (`AGENT.yaml`, `INSTRUCTIONS.md`, `MEMORY.md`, and the profiler's three skills). These describe how each agent should behave; there is no runtime that runs them against an LLM.
- Stubbed: the parsing layer (`src/auto_kg/parsing`), the orchestrator (`src/auto_kg/orchestrator`), and the MCP server generator (`src/auto_kg/mcp`) are present as docstring-only modules.
- Not present: any CLI or end-to-end driver, the cross-reference resolver, the temporal version and amendment processor, the MCP generation logic, and the agent learning loop. The landscape doc lists these as work to build and sketches a phased plan for them.

The original project description calls the output "perfectly representative." That is the design goal and the standard the validator is meant to enforce, not a property the current code achieves; the corpus-to-graph path that would produce such output is not implemented yet. Treat this repository as the foundation layer and the design record for the system described in [docs/corpus-kg-landscape-analysis.md](docs/corpus-kg-landscape-analysis.md).

## License

MIT, as declared in `pyproject.toml`.

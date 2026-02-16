# Auto KG Constructor

## What This Project Is

An AI engineering team (agents + tools) that takes any authoritative document corpus, develops deep understanding of it, and produces a perfectly representative structured backend with clean APIs — so any other AI agent can reason over that corpus as well as a human expert who studied it for years.

We are Layer A (construction crew). The output serves Layer B (tenants). Our job is the building, not the occupants.

## Architecture

- **Agent paradigm**: OpenClaw-inspired. Each agent has `AGENT.yaml` (identity/config) + `INSTRUCTIONS.md` (operating manual) + `MEMORY.md` (learned patterns) + `skills/` directory with `SKILL.md` files.
- **Agent runtime**: `src/auto_kg/runtime/` loads agent definitions and provides execution context.
- **Core schema**: `src/auto_kg/core/` — KG nodes ARE structural elements (sections, paragraphs, terms, tables), edges ARE relationships (hierarchy, cross-ref, definition-usage, amendment-chain).
- **Parsing**: `src/auto_kg/parsing/` wraps Docling + PageIndex.
- **Orchestration**: `src/auto_kg/orchestrator/` coordinates the multi-agent pipeline.
- **Output**: `src/auto_kg/mcp/` generates MCP servers from completed KGs.

## Key Technical Decisions

- Python 3.12+ with `uv` for dependency management
- Neo4j Community Edition for graph storage (via Docker)
- Pydantic v2 for all data models
- Bi-temporal model: every node/edge carries `valid_from`/`valid_until` + `recorded_at`
- MCP as the output API standard

## Agent Pipeline

```
corpus-profiler → pipeline-generator → kg-builder → validator
                                                        ↓
                                              mcp-server-generator
```

## Commands

```bash
uv sync                          # Install dependencies
uv sync --extra dev              # Install with dev tools
docker compose up -d             # Start Neo4j
uv run pytest                    # Run tests
uv run ruff check src/           # Lint
uv run mypy src/                 # Type check
```

## Conventions

- Agent definitions live in `agents/`, Python code lives in `src/auto_kg/`
- Agent MEMORY.md files are gitignored (runtime-generated)
- Corpus data goes in `corpora/` (gitignored, too large)
- Tests mirror src structure: `tests/core/`, `tests/parsing/`, etc.

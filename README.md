# Auto KG Constructor

AI engineering agents that transform document corpora into perfectly representative, temporally-versioned knowledge graphs with auto-generated APIs.

**Status**: Proof of concept — validating core hypothesis with FRS 102.

## Quick Start

```bash
uv sync --extra dev
docker compose up -d
uv run python proof/01_parse.py
```

See [CLAUDE.md](CLAUDE.md) for architecture and [docs/](docs/) for the landscape analysis.

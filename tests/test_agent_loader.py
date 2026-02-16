"""Tests for the agent runtime loader."""

from pathlib import Path

from auto_kg.runtime.agent_loader import load_agent, load_all_agents, load_skill

AGENTS_DIR = Path(__file__).parent.parent / "agents"


def test_load_corpus_profiler():
    agent = load_agent(AGENTS_DIR / "corpus-profiler")
    assert agent.name == "corpus-profiler"
    assert agent.role == "engineering-agent"
    assert "parsed_documents" in agent.inputs
    assert "corpus_profile" in agent.outputs
    assert len(agent.skills) >= 3  # detect-numbering, detect-crossrefs, detect-formatting
    assert agent.instructions  # INSTRUCTIONS.md loaded


def test_load_all_agents():
    agents = load_all_agents(AGENTS_DIR)
    assert "corpus-profiler" in agents
    assert "pipeline-generator" in agents
    assert "kg-builder" in agents
    assert "validator" in agents
    assert "orchestrator" in agents


def test_skill_loading():
    skill = load_skill(AGENTS_DIR / "corpus-profiler" / "skills" / "detect-numbering")
    assert skill is not None
    assert skill.name == "detect-numbering"
    assert skill.description  # From frontmatter
    assert skill.instructions  # Markdown body


def test_agent_dependencies():
    agents = load_all_agents(AGENTS_DIR)
    # Verify the pipeline dependency chain
    assert agents["corpus-profiler"].config.get("depends_on") == []
    assert "corpus-profiler" in agents["pipeline-generator"].config.get("depends_on", [])
    assert "pipeline-generator" in agents["kg-builder"].config.get("depends_on", [])
    assert "kg-builder" in agents["validator"].config.get("depends_on", [])

"""Loads agent definitions from the agents/ directory.

Each agent is a directory containing:
  - AGENT.yaml     — identity, role, capabilities, model config
  - INSTRUCTIONS.md — operating manual (injected into system prompt)
  - MEMORY.md      — persistent learned patterns (read/write at runtime)
  - skills/        — directory of SKILL.md files (discoverable capabilities)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SkillDef:
    """A loaded skill definition from a SKILL.md file."""

    name: str
    description: str
    instructions: str  # The markdown body
    path: Path


@dataclass
class AgentDef:
    """A loaded agent definition from an AGENT.yaml + associated files."""

    name: str
    description: str
    role: str
    model: str
    inputs: list[str]
    outputs: list[str]
    instructions: str  # From INSTRUCTIONS.md
    memory: str  # From MEMORY.md (mutable at runtime)
    skills: list[SkillDef] = field(default_factory=list)
    config: dict = field(default_factory=dict)  # Raw AGENT.yaml
    path: Path = field(default_factory=lambda: Path("."))


def load_skill(skill_dir: Path) -> SkillDef | None:
    """Load a single SKILL.md from a skill directory."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return None

    text = skill_file.read_text()

    # Parse YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1])
            body = parts[2].strip()
        else:
            frontmatter = {}
            body = text
    else:
        frontmatter = {}
        body = text

    return SkillDef(
        name=frontmatter.get("name", skill_dir.name),
        description=frontmatter.get("description", ""),
        instructions=body,
        path=skill_dir,
    )


def load_agent(agent_dir: Path) -> AgentDef:
    """Load a complete agent definition from a directory."""
    # Load AGENT.yaml
    agent_yaml = agent_dir / "AGENT.yaml"
    if not agent_yaml.exists():
        raise FileNotFoundError(f"No AGENT.yaml in {agent_dir}")

    config = yaml.safe_load(agent_yaml.read_text())

    # Load INSTRUCTIONS.md
    instructions_file = agent_dir / "INSTRUCTIONS.md"
    instructions = instructions_file.read_text() if instructions_file.exists() else ""

    # Load MEMORY.md
    memory_file = agent_dir / "MEMORY.md"
    memory = memory_file.read_text() if memory_file.exists() else ""

    # Discover and load skills
    skills: list[SkillDef] = []
    skills_dir = agent_dir / "skills"
    if skills_dir.exists():
        for skill_path in sorted(skills_dir.iterdir()):
            if skill_path.is_dir():
                skill = load_skill(skill_path)
                if skill:
                    skills.append(skill)

    return AgentDef(
        name=config.get("name", agent_dir.name),
        description=config.get("description", ""),
        role=config.get("role", "engineering-agent"),
        model=config.get("model", "claude-sonnet-4-5"),
        inputs=config.get("inputs", []),
        outputs=config.get("outputs", []),
        instructions=instructions,
        memory=memory,
        skills=skills,
        config=config,
        path=agent_dir,
    )


def load_all_agents(agents_root: Path) -> dict[str, AgentDef]:
    """Load all agents from the agents/ directory."""
    agents = {}
    if not agents_root.exists():
        return agents

    for agent_path in sorted(agents_root.iterdir()):
        if agent_path.is_dir() and (agent_path / "AGENT.yaml").exists():
            agent = load_agent(agent_path)
            agents[agent.name] = agent

    return agents

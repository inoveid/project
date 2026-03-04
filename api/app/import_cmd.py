"""CLI command for importing teams and agents from filesystem.

Usage:
    python -m app.import_cmd /path/to/teams/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.agent import Agent
from app.models.team import Team

logger = logging.getLogger(__name__)


@dataclass
class ImportStats:
    teams_created: int = 0
    teams_skipped: int = 0
    agents_created: int = 0
    agents_skipped: int = 0
    errors: list[str] = field(default_factory=list)


def parse_team_json(team_dir: Path) -> dict:
    """Read and parse team.json from a team directory."""
    team_json_path = team_dir / "team.json"
    if not team_json_path.exists():
        raise FileNotFoundError(f"team.json not found in {team_dir}")
    with open(team_json_path, encoding="utf-8") as f:
        return json.loads(f.read())


def discover_agents(team_dir: Path) -> list[dict]:
    """Discover agent directories within a team's agents/ folder."""
    agents_dir = team_dir / "agents"
    if not agents_dir.exists():
        return []
    result = []
    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        claude_md = agent_dir / "CLAUDE.md"
        if not claude_md.exists():
            continue
        result.append({
            "name": agent_dir.name,
            "system_prompt": claude_md.read_text(encoding="utf-8"),
        })
    return result


def get_agent_role(team_data: dict, agent_name: str) -> str:
    """Extract agent role from team.json agents section, or default."""
    agents_section = team_data.get("agents", {})
    agent_info = agents_section.get(agent_name, {})
    if isinstance(agent_info, dict):
        return agent_info.get("role", "agent")
    return "agent"


async def find_team_by_name(
    db: AsyncSession, name: str
) -> Team | None:
    """Find a team by name."""
    stmt = select(Team).where(Team.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_agent_by_name(
    db: AsyncSession, team_id: uuid.UUID, name: str
) -> Agent | None:
    """Find an agent by name within a team."""
    stmt = select(Agent).where(Agent.team_id == team_id, Agent.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def import_team(
    db: AsyncSession,
    team_dir: Path,
    stats: ImportStats,
) -> None:
    """Import a single team and its agents from a directory."""
    team_name = team_dir.name
    try:
        team_data = parse_team_json(team_dir)
    except FileNotFoundError:
        stats.errors.append(f"Skipping {team_name}: no team.json")
        return
    except json.JSONDecodeError as exc:
        stats.errors.append(f"Skipping {team_name}: invalid team.json ({exc})")
        return

    existing_team = await find_team_by_name(db, team_data.get("name", team_name))
    if existing_team is not None:
        logger.info("Team '%s' already exists, skipping", existing_team.name)
        stats.teams_skipped += 1
        team = existing_team
    else:
        team = Team(
            name=team_data.get("name", team_name),
            description=team_data.get("description"),
            project_scoped=team_data.get("project_scoped", False),
        )
        db.add(team)
        await db.flush()
        logger.info("Created team '%s'", team.name)
        stats.teams_created += 1

    agents = discover_agents(team_dir)
    for agent_info in agents:
        existing_agent = await find_agent_by_name(db, team.id, agent_info["name"])
        if existing_agent is not None:
            logger.info(
                "  Agent '%s' already exists in team '%s', skipping",
                agent_info["name"],
                team.name,
            )
            stats.agents_skipped += 1
            continue

        role = get_agent_role(team_data, agent_info["name"])
        agent = Agent(
            team_id=team.id,
            name=agent_info["name"],
            role=role,
            system_prompt=agent_info["system_prompt"],
            allowed_tools=[],
            config={},
        )
        db.add(agent)
        logger.info("  Created agent '%s' (role: %s)", agent.name, role)
        stats.agents_created += 1


async def run_import(teams_path: Path) -> ImportStats:
    """Import all teams from a directory."""
    if not teams_path.exists():
        raise FileNotFoundError(f"Directory not found: {teams_path}")
    if not teams_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {teams_path}")

    stats = ImportStats()

    async with async_session() as db:
        for team_dir in sorted(teams_path.iterdir()):
            if not team_dir.is_dir():
                continue
            await import_team(db, team_dir, stats)
        await db.commit()

    return stats


def print_summary(stats: ImportStats) -> None:
    """Print import summary to stdout."""
    print("\n=== Import Summary ===")
    print(f"Teams created:  {stats.teams_created}")
    print(f"Teams skipped:  {stats.teams_skipped}")
    print(f"Agents created: {stats.agents_created}")
    print(f"Agents skipped: {stats.agents_skipped}")
    if stats.errors:
        print(f"\nErrors ({len(stats.errors)}):")
        for err in stats.errors:
            print(f"  - {err}")
    print("=====================")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Import teams and agents from filesystem"
    )
    parser.add_argument(
        "teams_dir",
        type=Path,
        help="Path to teams/ directory",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    stats = asyncio.run(run_import(args.teams_dir))
    print_summary(stats)

    if stats.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.import_cmd import (
    ImportStats,
    discover_agents,
    get_agent_role,
    import_team,
    parse_team_json,
    print_summary,
    run_import,
)


@pytest.fixture
def teams_dir(tmp_path):
    """Create a realistic teams/ directory structure."""
    team_dir = tmp_path / "my-team"
    team_dir.mkdir()
    team_json = {
        "name": "my-team",
        "description": "Test team",
        "project_scoped": True,
        "agents": {
            "coder": {"role": "developer"},
            "reviewer": {"role": "reviewer"},
        },
    }
    (team_dir / "team.json").write_text(json.dumps(team_json))

    agents_dir = team_dir / "agents"
    agents_dir.mkdir()

    coder_dir = agents_dir / "coder"
    coder_dir.mkdir()
    (coder_dir / "CLAUDE.md").write_text("You are a coder agent.")

    reviewer_dir = agents_dir / "reviewer"
    reviewer_dir.mkdir()
    (reviewer_dir / "CLAUDE.md").write_text("You are a reviewer agent.")

    return tmp_path


@pytest.fixture
def empty_team_dir(tmp_path):
    """Team directory with team.json but no agents."""
    team_dir = tmp_path / "empty-team"
    team_dir.mkdir()
    team_json = {"name": "empty-team", "description": "No agents"}
    (team_dir / "team.json").write_text(json.dumps(team_json))
    return tmp_path


# --- parse_team_json ---


def test_parse_team_json(teams_dir):
    team_dir = teams_dir / "my-team"
    data = parse_team_json(team_dir)
    assert data["name"] == "my-team"
    assert data["project_scoped"] is True


def test_parse_team_json_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_team_json(tmp_path / "nonexistent")


# --- discover_agents ---


def test_discover_agents(teams_dir):
    agents = discover_agents(teams_dir / "my-team")
    assert len(agents) == 2
    names = [a["name"] for a in agents]
    assert "coder" in names
    assert "reviewer" in names
    coder = next(a for a in agents if a["name"] == "coder")
    assert coder["system_prompt"] == "You are a coder agent."


def test_discover_agents_no_agents_dir(tmp_path):
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    agents = discover_agents(team_dir)
    assert agents == []


def test_discover_agents_skips_files(teams_dir):
    """Files (not directories) in agents/ should be skipped."""
    agents_dir = teams_dir / "my-team" / "agents"
    (agents_dir / "README.md").write_text("ignore me")
    agents = discover_agents(teams_dir / "my-team")
    names = [a["name"] for a in agents]
    assert "README.md" not in names


def test_discover_agents_skips_dir_without_claude_md(teams_dir):
    """Agent dirs without CLAUDE.md should be skipped."""
    agents_dir = teams_dir / "my-team" / "agents"
    empty_agent = agents_dir / "broken-agent"
    empty_agent.mkdir()
    agents = discover_agents(teams_dir / "my-team")
    names = [a["name"] for a in agents]
    assert "broken-agent" not in names


# --- get_agent_role ---


def test_get_agent_role_from_team_data():
    team_data = {"agents": {"coder": {"role": "developer"}}}
    assert get_agent_role(team_data, "coder") == "developer"


def test_get_agent_role_default():
    team_data = {"agents": {}}
    assert get_agent_role(team_data, "unknown") == "agent"


def test_get_agent_role_no_agents_section():
    team_data = {}
    assert get_agent_role(team_data, "coder") == "agent"


# --- import_team ---


@pytest.mark.asyncio
async def test_import_team_creates_new(teams_dir):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.flush = AsyncMock()

    stats = ImportStats()
    await import_team(db, teams_dir / "my-team", stats)

    assert stats.teams_created == 1
    assert stats.teams_skipped == 0
    assert stats.agents_created == 2
    assert stats.agents_skipped == 0
    assert db.add.call_count == 3  # 1 team + 2 agents


@pytest.mark.asyncio
async def test_import_team_skips_existing(teams_dir):
    existing_team = MagicMock()
    existing_team.id = "fake-uuid"
    existing_team.name = "my-team"

    call_count = 0

    def mock_scalar(return_value=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # find_team_by_name → existing team
            return MagicMock(scalar_one_or_none=MagicMock(return_value=existing_team))
        # find_agent_by_name → not found
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=lambda stmt: mock_scalar())
    db.flush = AsyncMock()

    stats = ImportStats()
    await import_team(db, teams_dir / "my-team", stats)

    assert stats.teams_created == 0
    assert stats.teams_skipped == 1
    assert stats.agents_created == 2


@pytest.mark.asyncio
async def test_import_team_no_team_json(tmp_path):
    team_dir = tmp_path / "no-json-team"
    team_dir.mkdir()

    db = AsyncMock()
    stats = ImportStats()
    await import_team(db, team_dir, stats)

    assert stats.teams_created == 0
    assert len(stats.errors) == 1
    assert "no team.json" in stats.errors[0]


@pytest.mark.asyncio
async def test_import_team_invalid_json(tmp_path):
    team_dir = tmp_path / "bad-json-team"
    team_dir.mkdir()
    (team_dir / "team.json").write_text("{invalid json")

    db = AsyncMock()
    stats = ImportStats()
    await import_team(db, team_dir, stats)

    assert stats.teams_created == 0
    assert len(stats.errors) == 1
    assert "invalid team.json" in stats.errors[0]


# --- run_import ---


@pytest.mark.asyncio
async def test_run_import_not_found():
    with pytest.raises(FileNotFoundError):
        await run_import(Path("/nonexistent/path"))


@pytest.mark.asyncio
async def test_run_import_not_a_directory(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a dir")
    with pytest.raises(NotADirectoryError):
        await run_import(file_path)


# --- print_summary ---


def test_print_summary_clean(capsys):
    stats = ImportStats(teams_created=2, agents_created=5)
    print_summary(stats)
    output = capsys.readouterr().out
    assert "Teams created:  2" in output
    assert "Agents created: 5" in output
    assert "Errors" not in output


def test_print_summary_with_errors(capsys):
    stats = ImportStats(errors=["bad thing"])
    print_summary(stats)
    output = capsys.readouterr().out
    assert "Errors (1):" in output
    assert "bad thing" in output

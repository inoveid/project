"""Tests for app.services.utils.handoff — handoff utilities."""

from unittest.mock import MagicMock

from app.services.utils.handoff import (
    build_agent_prompt,
    format_handoff_instructions,
    parse_handoff_block,
)


# --- parse_handoff_block ---


def test_parse_handoff_block_valid():
    text = 'Some response text\n```handoff\n{"to": "Reviewer", "message": "Please review"}\n```'
    result = parse_handoff_block(text)
    assert result == {"to": "Reviewer", "message": "Please review"}


def test_parse_handoff_block_invalid_json():
    text = "```handoff\n{not valid json}\n```"
    result = parse_handoff_block(text)
    assert result is None


def test_parse_handoff_block_missing_fields():
    text = '```handoff\n{"to": "Reviewer"}\n```'
    assert parse_handoff_block(text) is None

    text2 = '```handoff\n{"message": "do stuff"}\n```'
    assert parse_handoff_block(text2) is None


def test_parse_handoff_block_no_block():
    text = "Just a regular response with no handoff block at all."
    assert parse_handoff_block(text) is None


def test_parse_handoff_block_in_middle_of_text():
    text = (
        "I have completed the implementation.\n\n"
        "Here is a summary of changes.\n\n"
        '```handoff\n{"to": "QA", "message": "Please run tests"}\n```\n'
    )
    result = parse_handoff_block(text)
    assert result == {"to": "QA", "message": "Please run tests"}


def test_parse_handoff_block_non_string_fields():
    text = '```handoff\n{"to": 123, "message": "test"}\n```'
    assert parse_handoff_block(text) is None

    text2 = '```handoff\n{"to": "Agent", "message": null}\n```'
    assert parse_handoff_block(text2) is None


# --- format_handoff_instructions ---


def _make_agent(name: str, role: str, description: str = "") -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.role = role
    agent.description = description
    return agent


def test_format_handoff_instructions_single_target():
    targets = [_make_agent("Reviewer", "reviewer", "Reviews code")]
    result = format_handoff_instructions(targets)
    assert "**Reviewer** (reviewer)" in result
    assert "Reviews code" in result
    assert "```handoff" in result


def test_format_handoff_instructions_multiple_targets():
    targets = [
        _make_agent("Reviewer", "reviewer", "Reviews code"),
        _make_agent("QA", "tester"),
    ]
    result = format_handoff_instructions(targets)
    assert "**Reviewer** (reviewer) — Reviews code" in result
    assert "**QA** (tester)" in result
    # No description for QA — no dash
    assert "**QA** (tester) —" not in result


def test_format_handoff_instructions_empty_list():
    result = format_handoff_instructions([])
    assert "Available Handoff Targets" in result
    assert "```handoff" in result


# --- build_agent_prompt ---


def _make_full_agent(
    name: str, system_prompt: str, config: dict | None = None, description: str = "",
) -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.system_prompt = system_prompt
    agent.config = config
    agent.description = description
    agent.role = "agent"
    return agent


def test_build_agent_prompt_basic():
    agent = _make_full_agent("Dev", "You are a developer.")
    result = build_agent_prompt(agent, [], [])
    assert result == "You are a developer."


def test_build_agent_prompt_with_chain():
    agent = _make_full_agent("Reviewer", "You review code.")
    chain = [("Dev", "Reviewer")]
    result = build_agent_prompt(agent, chain, [])
    assert "Handoff Chain Context" in result
    assert "Dev→Reviewer" in result
    assert "Reviewer (you)" in result


def test_build_agent_prompt_with_workdir():
    agent = _make_full_agent("Dev", "You code.", config={"workdir": "/project"})
    result = build_agent_prompt(agent, [], [])
    assert "Working directory: /project" in result


def test_build_agent_prompt_with_sub_targets():
    agent = _make_full_agent("Dev", "You code.")
    targets = [_make_agent("QA", "tester", "Runs tests")]
    result = build_agent_prompt(agent, [], targets)
    assert "Available Handoff Targets" in result
    assert "**QA** (tester)" in result


def test_build_agent_prompt_no_workdir_in_config():
    agent = _make_full_agent("Dev", "You code.", config={})
    result = build_agent_prompt(agent, [], [])
    assert "Working directory" not in result


def test_build_agent_prompt_none_config():
    agent = _make_full_agent("Dev", "You code.", config=None)
    result = build_agent_prompt(agent, [], [])
    assert "Working directory" not in result

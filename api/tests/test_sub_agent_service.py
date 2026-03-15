"""Tests for sub_agent_service — spawn parsing, template matching, result formatting."""
import pytest
from app.services.sub_agent_service import (
    parse_spawn_requests,
    find_template,
    format_spawn_tools_prompt,
    format_sub_agent_results,
    SubAgentResult,
    MAX_SUB_AGENTS_PER_TURN,
)


class TestParseSpawnRequests:
    def test_empty_text(self):
        assert parse_spawn_requests("") == []
        assert parse_spawn_requests("no spawn blocks here") == []

    def test_spawn_agent_block(self):
        text = '''Some text
```spawn_agent
{"role": "researcher", "task": "Find OAuth examples"}
```
More text'''
        reqs = parse_spawn_requests(text)
        assert len(reqs) == 1
        assert reqs[0].role == "researcher"
        assert reqs[0].task == "Find OAuth examples"
        assert not reqs[0].is_custom

    def test_spawn_custom_block(self):
        text = '''```spawn_custom
{"name": "auditor", "instructions": "You are a security expert", "task": "Check SQL injection", "tools": ["Bash", "Read"]}
```'''
        reqs = parse_spawn_requests(text)
        assert len(reqs) == 1
        assert reqs[0].is_custom
        assert reqs[0].custom_name == "auditor"
        assert reqs[0].custom_instructions == "You are a security expert"
        assert reqs[0].task == "Check SQL injection"
        assert reqs[0].custom_tools == ["Bash", "Read"]

    def test_multiple_blocks(self):
        text = '''```spawn_agent
{"role": "r1", "task": "t1"}
```
some text
```spawn_agent
{"role": "r2", "task": "t2"}
```
```spawn_custom
{"name": "c1", "instructions": "inst", "task": "t3"}
```'''
        reqs = parse_spawn_requests(text)
        assert len(reqs) == 3
        assert reqs[0].role == "r1"
        assert reqs[1].role == "r2"
        assert reqs[2].is_custom

    def test_max_limit(self):
        blocks = "\n".join(
            f'```spawn_agent\n{{"role": "r{i}", "task": "t{i}"}}\n```'
            for i in range(10)
        )
        reqs = parse_spawn_requests(blocks)
        assert len(reqs) == MAX_SUB_AGENTS_PER_TURN

    def test_invalid_json_skipped(self):
        text = '''```spawn_agent
not valid json
```
```spawn_agent
{"role": "valid", "task": "ok"}
```'''
        reqs = parse_spawn_requests(text)
        assert len(reqs) == 1
        assert reqs[0].role == "valid"

    def test_missing_fields_skipped(self):
        text = '''```spawn_agent
{"role": "only_role"}
```'''
        reqs = parse_spawn_requests(text)
        assert len(reqs) == 0


class TestFindTemplate:
    def test_finds_by_role(self):
        templates = [
            {"id": "t1", "role": "researcher", "name": "Research Agent", "system_prompt": "...", "allowed_tools": ["Read"]},
            {"id": "t2", "role": "coder", "name": "Code Agent", "system_prompt": "...", "allowed_tools": ["Bash"]},
        ]
        t = find_template(templates, "researcher")
        assert t is not None
        assert t.name == "Research Agent"

    def test_case_insensitive(self):
        templates = [{"id": "t1", "role": "Researcher", "name": "R", "system_prompt": "sp", "allowed_tools": []}]
        assert find_template(templates, "researcher") is not None
        assert find_template(templates, "RESEARCHER") is not None

    def test_not_found(self):
        templates = [{"id": "t1", "role": "coder", "name": "C", "system_prompt": "sp", "allowed_tools": []}]
        assert find_template(templates, "designer") is None

    def test_empty_templates(self):
        assert find_template([], "any") is None


class TestFormatSubAgentResults:
    def test_empty(self):
        assert format_sub_agent_results([]) == ""

    def test_success_result(self):
        results = [SubAgentResult(role="researcher", name="R1", output="Found 5 examples", success=True)]
        text = format_sub_agent_results(results)
        assert "R1" in text
        assert "researcher" in text
        assert "Found 5 examples" in text
        assert "OK" in text

    def test_failed_result(self):
        results = [SubAgentResult(role="coder", name="C1", output="", success=False, error="Timeout")]
        text = format_sub_agent_results(results)
        assert "FAILED" in text
        assert "Timeout" in text

    def test_mixed_results(self):
        results = [
            SubAgentResult(role="r1", name="N1", output="ok", success=True),
            SubAgentResult(role="r2", name="N2", output="", success=False, error="err"),
        ]
        text = format_sub_agent_results(results)
        assert "OK" in text
        assert "FAILED" in text


class TestFormatSpawnToolsPrompt:
    def test_with_templates(self):
        templates = [{"role": "researcher", "description": "Finds info"}]
        prompt = format_spawn_tools_prompt(templates)
        assert "researcher" in prompt
        assert "Finds info" in prompt
        assert "spawn_agent" in prompt
        assert "spawn_custom" in prompt

    def test_without_templates(self):
        prompt = format_spawn_tools_prompt([])
        assert "spawn_custom" in prompt
        assert "Custom" in prompt

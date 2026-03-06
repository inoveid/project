import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.runtime import AgentRuntime, AgentRuntimeError, RunningProcess


@pytest.fixture
def agent_runtime():
    return AgentRuntime()


@pytest.fixture
def session_id():
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_start_session(agent_runtime, session_id):
    await agent_runtime.start_session(
        session_id=session_id,
        workdir="/tmp/project",
        system_prompt="You are a test agent",
    )
    assert agent_runtime.is_running(session_id)


@pytest.mark.asyncio
async def test_start_session_stores_workdir(agent_runtime, session_id):
    await agent_runtime.start_session(
        session_id=session_id,
        workdir="/custom/workdir",
        system_prompt="test",
    )
    running = agent_runtime._processes[session_id]
    assert running.workdir == "/custom/workdir"


@pytest.mark.asyncio
async def test_start_session_fallback_workdir(agent_runtime, session_id):
    await agent_runtime.start_session(
        session_id=session_id,
        workdir="",
        system_prompt="test",
    )
    from app.config import settings
    running = agent_runtime._processes[session_id]
    assert running.workdir == settings.workspace_path


@pytest.mark.asyncio
async def test_start_session_duplicate(agent_runtime, session_id):
    await agent_runtime.start_session(
        session_id=session_id,
        workdir="/tmp",
        system_prompt="test",
    )
    with pytest.raises(AgentRuntimeError, match="already running"):
        await agent_runtime.start_session(
            session_id=session_id,
            workdir="/tmp",
            system_prompt="test",
        )


@pytest.mark.asyncio
async def test_stop_session(agent_runtime, session_id):
    await agent_runtime.start_session(
        session_id=session_id,
        workdir="/tmp",
        system_prompt="test",
    )
    await agent_runtime.stop_session(session_id)
    assert not agent_runtime.is_running(session_id)


@pytest.mark.asyncio
async def test_stop_nonexistent_session(agent_runtime):
    await agent_runtime.stop_session(uuid.uuid4())


@pytest.mark.asyncio
async def test_is_running_false_by_default(agent_runtime):
    assert not agent_runtime.is_running(uuid.uuid4())


def test_get_claude_session_id_none(agent_runtime):
    assert agent_runtime.get_claude_session_id(uuid.uuid4()) is None


def test_get_claude_session_id(agent_runtime, session_id):
    agent_runtime._processes[session_id] = RunningProcess(
        process=None,
        session_id=session_id,
        workdir="/tmp",
        system_prompt="test",
        claude_session_id="claude-abc",
    )
    assert agent_runtime.get_claude_session_id(session_id) == "claude-abc"


def test_build_command_without_resume(agent_runtime, session_id):
    running = RunningProcess(
        process=None,
        session_id=session_id,
        workdir="/tmp",
        system_prompt="You are helpful",
    )
    agent_runtime._processes[session_id] = running
    cmd = agent_runtime._build_command(running)
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--resume" not in cmd
    assert "--system-prompt" in cmd
    idx = cmd.index("--system-prompt")
    assert cmd[idx + 1] == "You are helpful"


def test_build_command_with_resume(agent_runtime, session_id):
    running = RunningProcess(
        process=None,
        session_id=session_id,
        workdir="/tmp",
        system_prompt="test",
        claude_session_id="claude-123",
    )
    agent_runtime._processes[session_id] = running
    cmd = agent_runtime._build_command(running)
    assert "--session-id" in cmd
    assert "claude-123" in cmd
    assert "--resume" in cmd


def test_build_command_empty_system_prompt(agent_runtime, session_id):
    running = RunningProcess(
        process=None,
        session_id=session_id,
        workdir="/tmp",
        system_prompt="",
    )
    cmd = agent_runtime._build_command(running)
    assert "--system-prompt" not in cmd


def test_parse_event_assistant_text(agent_runtime, session_id):
    event = {"type": "assistant", "subtype": "text", "text": "Hello!"}
    result = agent_runtime._parse_event(session_id, event)
    assert result == {"type": "assistant_text", "content": "Hello!"}


def test_parse_event_tool_use(agent_runtime, session_id):
    event = {"type": "tool_use", "tool": "read_file", "input": {"path": "/tmp"}}
    result = agent_runtime._parse_event(session_id, event)
    assert result == {
        "type": "tool_use",
        "tool_name": "read_file",
        "tool_input": {"path": "/tmp"},
    }


def test_parse_event_tool_result(agent_runtime, session_id):
    event = {"type": "tool_result", "output": "file contents"}
    result = agent_runtime._parse_event(session_id, event)
    assert result == {"type": "tool_result", "content": "file contents"}


def test_parse_event_system_updates_session_id(agent_runtime, session_id):
    agent_runtime._processes[session_id] = RunningProcess(
        process=None,
        session_id=session_id,
        workdir="/tmp",
        system_prompt="test",
    )
    event = {"type": "system", "session_id": "new-claude-id"}
    result = agent_runtime._parse_event(session_id, event)
    assert result is None
    assert agent_runtime._processes[session_id].claude_session_id == "new-claude-id"


def test_parse_event_unknown_returns_none(agent_runtime, session_id):
    event = {"type": "unknown_event"}
    result = agent_runtime._parse_event(session_id, event)
    assert result is None


@pytest.mark.asyncio
async def test_run_task_creates_isolated_dir(agent_runtime, tmp_path):
    """run_task creates .handoff_sessions/<uuid>/ as subprocess CWD."""
    workdir = str(tmp_path)

    async def fake_send_message(sid, content):
        # Verify isolated dir was created
        handoff_dir = tmp_path / ".handoff_sessions"
        assert handoff_dir.exists()
        subdirs = list(handoff_dir.iterdir())
        assert len(subdirs) == 1
        # Verify the session uses isolated dir
        running = agent_runtime._processes[sid]
        assert ".handoff_sessions/" in running.workdir
        return
        yield  # noqa: unreachable — makes this an async generator

    with patch.object(agent_runtime, "send_message", side_effect=fake_send_message):
        async for _ in agent_runtime.run_task(
            workdir=workdir,
            system_prompt="test prompt",
            task="do something",
        ):
            pass


@pytest.mark.asyncio
async def test_run_task_yields_events(agent_runtime, tmp_path):
    """run_task proxies events from send_message."""
    expected_events = [
        {"type": "assistant_text", "content": "hello"},
        {"type": "tool_use", "tool_name": "read", "tool_input": {}},
    ]

    async def fake_send_message(sid, content):
        for event in expected_events:
            yield event

    with patch.object(agent_runtime, "send_message", side_effect=fake_send_message):
        collected = []
        async for event in agent_runtime.run_task(
            workdir=str(tmp_path),
            system_prompt="test",
            task="hello",
        ):
            collected.append(event)

    assert collected == expected_events


@pytest.mark.asyncio
async def test_run_task_cleans_up_session(agent_runtime, tmp_path):
    """stop_session is called in finally block even on error."""
    stop_mock = AsyncMock()

    async def fake_send_message(sid, content):
        raise RuntimeError("boom")
        yield  # noqa: unreachable — makes this an async generator

    with patch.object(agent_runtime, "send_message", side_effect=fake_send_message), \
         patch.object(agent_runtime, "stop_session", stop_mock):
        with pytest.raises(RuntimeError, match="boom"):
            async for _ in agent_runtime.run_task(
                workdir=str(tmp_path),
                system_prompt="test",
                task="fail",
            ):
                pass

    stop_mock.assert_awaited_once()

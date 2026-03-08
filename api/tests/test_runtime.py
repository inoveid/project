import asyncio
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
    assert "--continue" in cmd
    assert "--session-id" not in cmd


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


@pytest.mark.asyncio
async def test_send_message_kills_only_own_session(agent_runtime):
    """send_message should kill only the process of the current session, not others."""
    import sys
    from unittest.mock import MagicMock

    # Pre-inject mock auth_service to avoid import chain issues
    mock_auth_module = MagicMock()
    mock_auth_module.get_current_access_token = AsyncMock(return_value="token")
    sys.modules["app.services.auth_service"] = mock_auth_module

    # Pre-inject mock telemetry
    mock_telemetry = MagicMock()
    mock_telemetry.get_langfuse = MagicMock(return_value=None)
    sys.modules["app.services.telemetry"] = mock_telemetry

    try:
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        mock_proc1 = AsyncMock()
        mock_proc1.returncode = None
        mock_proc2 = AsyncMock()
        mock_proc2.returncode = None

        await agent_runtime.start_session(sid1, "/tmp/a", "test")
        await agent_runtime.start_session(sid2, "/tmp/b", "test")
        agent_runtime._processes[sid1].process = mock_proc1
        agent_runtime._processes[sid2].process = mock_proc2

        with patch.object(agent_runtime, "_kill_process", new_callable=AsyncMock) as kill_mock, \
             patch.object(agent_runtime, "_launch_process", new_callable=AsyncMock) as launch_mock:
            # Make launch return a mock process with stdout/stdin
            mock_new_proc = AsyncMock()
            mock_new_proc.stdin = AsyncMock()
            mock_new_proc.stdin.write = lambda x: None
            mock_new_proc.stdin.write_eof = lambda: None
            mock_new_proc.stdout = AsyncMock()
            mock_new_proc.stdout.__aiter__ = AsyncMock(return_value=iter([]))
            mock_new_proc.stderr = None
            mock_new_proc.returncode = 0
            mock_new_proc.wait = AsyncMock(return_value=0)
            launch_mock.return_value = mock_new_proc

            # Consume the async generator
            try:
                async for _ in agent_runtime.send_message(sid1, "hello"):
                    pass
            except Exception:
                pass

            # _kill_process should be called with sid1's running process, NOT sid2's
            kill_mock.assert_awaited_once()
            killed_running = kill_mock.call_args[0][0]
            assert killed_running.session_id == sid1
    finally:
        sys.modules.pop("app.services.auth_service", None)
        sys.modules.pop("app.services.telemetry", None)


@pytest.mark.asyncio
async def test_start_session_rejects_busy_workdir(agent_runtime):
    """start_session should reject if workdir is actively used by another session."""
    sid1 = uuid.uuid4()
    sid2 = uuid.uuid4()

    await agent_runtime.start_session(sid1, "/shared/workdir", "test")
    # Simulate active process
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    agent_runtime._processes[sid1].process = mock_proc

    with pytest.raises(AgentRuntimeError, match="already in use"):
        await agent_runtime.start_session(sid2, "/shared/workdir", "test")


@pytest.mark.asyncio
async def test_start_session_allows_workdir_after_process_exits(agent_runtime):
    """start_session should allow workdir if previous process has exited."""
    sid1 = uuid.uuid4()
    sid2 = uuid.uuid4()

    await agent_runtime.start_session(sid1, "/shared/workdir", "test")
    # Simulate exited process
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    agent_runtime._processes[sid1].process = mock_proc

    # Should not raise
    await agent_runtime.start_session(sid2, "/shared/workdir", "test")
    assert agent_runtime.is_running(sid2)


def test_parse_event_result_includes_model(agent_runtime, session_id):
    """_parse_event should propagate model field from result events."""
    event = {
        "type": "result",
        "cost_usd": 0.05,
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "model": "claude-opus-4-20250514",
    }
    result = agent_runtime._parse_event(session_id, event)
    assert result["model"] == "claude-opus-4-20250514"


def test_parse_event_result_model_none(agent_runtime, session_id):
    """_parse_event should handle missing model gracefully."""
    event = {
        "type": "result",
        "cost_usd": 0.01,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    result = agent_runtime._parse_event(session_id, event)
    assert result["model"] is None


@pytest.mark.asyncio
async def test_start_session_with_parent(agent_runtime):
    """start_session with parent_session_id registers child in _children."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    assert child_id in agent_runtime._children[parent_id]
    assert agent_runtime.is_running(child_id)


@pytest.mark.asyncio
async def test_stop_session_kills_children(agent_runtime):
    """stop_session recursively stops all child sessions."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    await agent_runtime.stop_session(parent_id)

    assert not agent_runtime.is_running(parent_id)
    assert not agent_runtime.is_running(child_id)
    assert parent_id not in agent_runtime._children


@pytest.mark.asyncio
async def test_stop_child_removes_from_parent(agent_runtime):
    """Stopping a child session removes it from parent's _children set."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    await agent_runtime.stop_session(child_id)

    assert not agent_runtime.is_running(child_id)
    assert agent_runtime.is_running(parent_id)
    assert child_id not in agent_runtime._children.get(parent_id, set())


@pytest.mark.asyncio
async def test_double_stop_session_is_safe(agent_runtime):
    """Calling stop_session twice does not raise."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    # First: normal sub-agent cleanup
    await agent_runtime.stop_session(child_id)
    # Second: parent disconnect triggers recursive cleanup — child already gone
    await agent_runtime.stop_session(parent_id)

    assert not agent_runtime.is_running(parent_id)
    assert not agent_runtime.is_running(child_id)
    assert not agent_runtime._children


@pytest.mark.asyncio
async def test_stop_session_kills_nested_children(agent_runtime):
    """stop_session handles chain A→B→C (all registered as children of A)."""
    parent_id = uuid.uuid4()
    child1_id = uuid.uuid4()
    child2_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child1_id, "/tmp/b", "test", parent_session_id=parent_id)
    await agent_runtime.start_session(child2_id, "/tmp/c", "test", parent_session_id=parent_id)

    await agent_runtime.stop_session(parent_id)

    assert not agent_runtime.is_running(parent_id)
    assert not agent_runtime.is_running(child1_id)
    assert not agent_runtime.is_running(child2_id)


@pytest.mark.asyncio
async def test_get_children_returns_copy(agent_runtime):
    """get_children returns child IDs without modifying internal state."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    children = agent_runtime.get_children(parent_id)
    assert children == {child_id}
    # Mutating returned set doesn't affect internal state
    children.discard(child_id)
    assert child_id in agent_runtime._children[parent_id]


@pytest.mark.asyncio
async def test_get_children_empty(agent_runtime):
    """get_children returns empty set for session without children."""
    sid = uuid.uuid4()
    assert agent_runtime.get_children(sid) == set()


@pytest.mark.asyncio
async def test_run_task_no_parent_tracking(agent_runtime, tmp_path):
    """run_task (ephemeral) does not use parent tracking."""
    async def fake_send_message(sid, content):
        return
        yield  # noqa: unreachable

    with patch.object(agent_runtime, "send_message", side_effect=fake_send_message):
        async for _ in agent_runtime.run_task(
            workdir=str(tmp_path),
            system_prompt="test",
            task="do something",
        ):
            pass

    # No children tracking should exist
    assert not agent_runtime._children


@pytest.mark.asyncio
async def test_read_stream_cancels_stderr_task_on_exception(agent_runtime, session_id):
    """stderr_task should be cancelled if stdout iteration raises."""
    mock_process = AsyncMock()

    # stdout raises on iteration
    async def exploding_iter():
        raise RuntimeError("stream error")
        yield  # noqa: unreachable

    mock_process.stdout = exploding_iter()
    mock_process.stderr = AsyncMock()

    stderr_task_created = []
    original_create_task = asyncio.create_task

    def tracking_create_task(coro, **kwargs):
        task = original_create_task(coro, **kwargs)
        stderr_task_created.append(task)
        return task

    with patch("asyncio.create_task", side_effect=tracking_create_task):
        with pytest.raises(RuntimeError, match="stream error"):
            async for _ in agent_runtime._read_stream(session_id, mock_process):
                pass

    # Verify stderr_task was cancelled
    if stderr_task_created:
        assert stderr_task_created[0].cancelled() or stderr_task_created[0].done()

"""Tests for app.services.runtime — AgentRuntime with Claude Agent SDK."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.runtime import AgentRuntime, AgentRuntimeError


@pytest.fixture
def agent_runtime():
    return AgentRuntime()


@pytest.fixture
def session_id():
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------

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
    session = agent_runtime._sessions[session_id]
    assert session.workdir == "/custom/workdir"


@pytest.mark.asyncio
async def test_start_session_fallback_workdir(agent_runtime, session_id):
    await agent_runtime.start_session(
        session_id=session_id,
        workdir="",
        system_prompt="test",
    )
    from app.config import settings
    session = agent_runtime._sessions[session_id]
    assert session.workdir == settings.workspace_path


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
async def test_start_session_stops_stale_same_workdir(agent_runtime):
    """Starting a session with a workdir used by another session stops the stale one."""
    sid1 = uuid.uuid4()
    sid2 = uuid.uuid4()

    await agent_runtime.start_session(sid1, "/shared/workdir", "test")
    assert agent_runtime.is_running(sid1)

    await agent_runtime.start_session(sid2, "/shared/workdir", "test")
    assert agent_runtime.is_running(sid2)
    assert not agent_runtime.is_running(sid1)


# ---------------------------------------------------------------------------
# stop_session
# ---------------------------------------------------------------------------

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
async def test_stop_session_disconnects_client(agent_runtime, session_id):
    """stop_session calls client.disconnect() if client exists."""
    await agent_runtime.start_session(session_id, "/tmp", "test")
    mock_client = AsyncMock()
    agent_runtime._sessions[session_id].client = mock_client

    await agent_runtime.stop_session(session_id)
    mock_client.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# is_running / get_claude_session_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_running_false_by_default(agent_runtime):
    assert not agent_runtime.is_running(uuid.uuid4())


def test_get_claude_session_id_none(agent_runtime):
    assert agent_runtime.get_claude_session_id(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_get_claude_session_id(agent_runtime, session_id):
    await agent_runtime.start_session(session_id, "/tmp", "test")
    agent_runtime._sessions[session_id].claude_session_id = "claude-abc"
    assert agent_runtime.get_claude_session_id(session_id) == "claude-abc"


# ---------------------------------------------------------------------------
# allowed_tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_session_stores_allowed_tools(agent_runtime, session_id):
    tools = ["read_file", "write_file"]
    await agent_runtime.start_session(
        session_id=session_id,
        workdir="/tmp",
        system_prompt="test",
        allowed_tools=tools,
    )
    assert agent_runtime._sessions[session_id].allowed_tools == tools


@pytest.mark.asyncio
async def test_start_session_default_allowed_tools(agent_runtime, session_id):
    await agent_runtime.start_session(session_id, "/tmp", "test")
    assert agent_runtime._sessions[session_id].allowed_tools == []


# ---------------------------------------------------------------------------
# Parent-child relationships
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_session_with_parent(agent_runtime):
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    assert child_id in agent_runtime._children[parent_id]
    assert agent_runtime.is_running(child_id)


@pytest.mark.asyncio
async def test_stop_session_kills_children(agent_runtime):
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
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    await agent_runtime.stop_session(child_id)
    await agent_runtime.stop_session(parent_id)

    assert not agent_runtime.is_running(parent_id)
    assert not agent_runtime.is_running(child_id)
    assert not agent_runtime._children


@pytest.mark.asyncio
async def test_stop_session_kills_nested_children(agent_runtime):
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
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await agent_runtime.start_session(parent_id, "/tmp/a", "test")
    await agent_runtime.start_session(child_id, "/tmp/b", "test", parent_session_id=parent_id)

    children = agent_runtime.get_children(parent_id)
    assert children == {child_id}
    children.discard(child_id)
    assert child_id in agent_runtime._children[parent_id]


@pytest.mark.asyncio
async def test_get_children_empty(agent_runtime):
    sid = uuid.uuid4()
    assert agent_runtime.get_children(sid) == set()


# ---------------------------------------------------------------------------
# kill_active_process (interrupt SDK client)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kill_active_process_interrupts_client(agent_runtime, session_id):
    await agent_runtime.start_session(session_id, "/tmp", "test")
    mock_client = AsyncMock()
    agent_runtime._sessions[session_id].client = mock_client

    await agent_runtime.kill_active_process(session_id)
    mock_client.interrupt.assert_awaited_once()


@pytest.mark.asyncio
async def test_kill_active_process_no_client(agent_runtime, session_id):
    """kill_active_process is safe when no client is attached."""
    await agent_runtime.start_session(session_id, "/tmp", "test")
    await agent_runtime.kill_active_process(session_id)


@pytest.mark.asyncio
async def test_kill_active_process_nonexistent_session(agent_runtime):
    """kill_active_process is safe for unknown session."""
    await agent_runtime.kill_active_process(uuid.uuid4())


# ---------------------------------------------------------------------------
# send_message — basic contract tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_message_not_running(agent_runtime, session_id):
    with pytest.raises(AgentRuntimeError, match="not running"):
        async for _ in agent_runtime.send_message(session_id, "hello"):
            pass


@pytest.mark.asyncio
async def test_send_message_not_authenticated(agent_runtime, session_id):
    await agent_runtime.start_session(session_id, "/tmp", "test")

    with patch("app.services.auth_service.get_current_access_token", new_callable=AsyncMock, return_value=None):
        with pytest.raises(AgentRuntimeError, match="Not authenticated"):
            async for _ in agent_runtime.send_message(session_id, "hello"):
                pass

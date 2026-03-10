import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services.workflow_service import (
    AgentNotInTeamError,
    DuplicateWorkflowError,
    TeamNotFoundError,
    WorkflowNotFoundError,
    create_workflow,
    delete_workflow,
    get_workflow,
    get_workflows,
    update_workflow,
    validate_workflow,
)


def _mock_db_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    scalars = MagicMock()
    scalars.all.return_value = value if isinstance(value, list) else [value]
    result.scalars.return_value = scalars
    return result


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_get_workflows_team_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    with pytest.raises(TeamNotFoundError):
        await get_workflows(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_workflows_returns_list():
    db = _make_db()
    team_id = uuid.uuid4()
    fake_wf = MagicMock()
    db.execute.side_effect = [
        _mock_db_result(team_id),
        _mock_db_result([fake_wf]),
    ]
    result = await get_workflows(db, team_id)
    assert result == [fake_wf]


@pytest.mark.asyncio
async def test_get_workflow_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    with pytest.raises(WorkflowNotFoundError):
        await get_workflow(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_workflow_success():
    db = _make_db()
    fake_wf = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake_wf
    db.execute.return_value = result_mock
    result = await get_workflow(db, uuid.uuid4())
    assert result is fake_wf


@pytest.mark.asyncio
async def test_create_workflow_team_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    data = WorkflowCreate(
        name="test",
        starting_agent_id=uuid.uuid4(),
        starting_prompt="go",
    )
    with pytest.raises(TeamNotFoundError):
        await create_workflow(db, uuid.uuid4(), data)


@pytest.mark.asyncio
async def test_create_workflow_agent_not_in_team():
    db = _make_db()
    team_id = uuid.uuid4()
    db.execute.side_effect = [
        _mock_db_result(team_id),
        _mock_db_result(None),
    ]
    data = WorkflowCreate(
        name="test",
        starting_agent_id=uuid.uuid4(),
        starting_prompt="go",
    )
    with pytest.raises(AgentNotInTeamError):
        await create_workflow(db, team_id, data)


@pytest.mark.asyncio
async def test_create_workflow_success():
    db = _make_db()
    team_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    db.execute.side_effect = [
        _mock_db_result(team_id),
        _mock_db_result(agent_id),
    ]
    data = WorkflowCreate(
        name="test",
        starting_agent_id=agent_id,
        starting_prompt="go",
    )
    result = await create_workflow(db, team_id, data)
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()
    assert result is not None


@pytest.mark.asyncio
async def test_create_workflow_duplicate():
    db = _make_db()
    team_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    db.execute.side_effect = [
        _mock_db_result(team_id),
        _mock_db_result(agent_id),
    ]
    db.commit.side_effect = IntegrityError("dup", {}, None)
    data = WorkflowCreate(
        name="test",
        starting_agent_id=agent_id,
        starting_prompt="go",
    )
    with pytest.raises(DuplicateWorkflowError):
        await create_workflow(db, team_id, data)
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_workflow_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    with pytest.raises(WorkflowNotFoundError):
        await delete_workflow(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_workflow_success():
    db = _make_db()
    fake_wf = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake_wf
    db.execute.return_value = result_mock
    await delete_workflow(db, uuid.uuid4())
    db.delete.assert_awaited_once_with(fake_wf)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_workflow():
    db = _make_db()
    fake_wf = MagicMock()
    fake_wf.starting_agent_id = uuid.uuid4()
    fake_wf.starting_prompt = "go"
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake_wf
    db.execute.return_value = result_mock
    assert await validate_workflow(db, uuid.uuid4()) is True

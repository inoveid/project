import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.workflow_edge import WorkflowEdgeCreate, WorkflowEdgeUpdate
from app.services.workflow_edge_service import (
    EdgeNotFoundError,
    WorkflowNotFoundError,
    create_edge,
    delete_edge,
    get_edges,
    update_edge,
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
async def test_get_edges_workflow_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    with pytest.raises(WorkflowNotFoundError):
        await get_edges(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_edges_returns_list():
    db = _make_db()
    wid = uuid.uuid4()
    fake_edge = MagicMock()
    db.execute.side_effect = [
        _mock_db_result(wid),
        _mock_db_result([fake_edge]),
    ]
    result = await get_edges(db, wid)
    assert result == [fake_edge]


@pytest.mark.asyncio
async def test_create_edge_workflow_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    data = WorkflowEdgeCreate(
        from_agent_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
    )
    with pytest.raises(WorkflowNotFoundError):
        await create_edge(db, uuid.uuid4(), data)


@pytest.mark.asyncio
async def test_create_edge_success():
    db = _make_db()
    wid = uuid.uuid4()
    db.execute.return_value = _mock_db_result(wid)
    data = WorkflowEdgeCreate(
        from_agent_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
        condition="status == 'done'",
        order=1,
        requires_approval=False,
    )
    result = await create_edge(db, wid, data)
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()
    assert result is not None


@pytest.mark.asyncio
async def test_update_edge_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    data = WorkflowEdgeUpdate(condition="x")
    with pytest.raises(EdgeNotFoundError):
        await update_edge(db, uuid.uuid4(), data)


@pytest.mark.asyncio
async def test_update_edge_success():
    db = _make_db()
    fake_edge = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake_edge
    db.execute.return_value = result_mock

    data = WorkflowEdgeUpdate(condition="new_cond", requires_approval=False)
    result = await update_edge(db, uuid.uuid4(), data)
    assert fake_edge.condition == "new_cond"
    assert fake_edge.requires_approval is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_edge_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    with pytest.raises(EdgeNotFoundError):
        await delete_edge(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_edge_success():
    db = _make_db()
    fake_edge = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake_edge
    db.execute.return_value = result_mock
    await delete_edge(db, uuid.uuid4())
    db.delete.assert_awaited_once_with(fake_edge)
    db.commit.assert_awaited_once()

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.agent_link import AgentLinkCreate, LinkType
from app.services.agent_link_service import (
    AgentNotInTeamError,
    DuplicateLinkError,
    LinkNotFoundError,
    TeamNotFoundError,
    create_link,
    delete_link,
    get_links,
)


def _mock_db_result(value):
    """Create a mock result that returns value from scalar_one_or_none / scalars."""
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
async def test_get_links_team_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    with pytest.raises(TeamNotFoundError):
        await get_links(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_links_returns_list():
    db = _make_db()
    team_id = uuid.uuid4()
    fake_link = MagicMock()
    # First call: team exists check, second call: select links
    team_result = _mock_db_result(team_id)
    links_result = _mock_db_result([fake_link])
    db.execute.side_effect = [team_result, links_result]

    result = await get_links(db, team_id)
    assert result == [fake_link]


@pytest.mark.asyncio
async def test_create_link_team_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    data = AgentLinkCreate(
        from_agent_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
        link_type=LinkType.handoff,
    )
    with pytest.raises(TeamNotFoundError):
        await create_link(db, uuid.uuid4(), data)


@pytest.mark.asyncio
async def test_create_link_from_agent_not_in_team():
    db = _make_db()
    team_id = uuid.uuid4()
    # team exists → ok, from_agent check → not found
    team_result = _mock_db_result(team_id)
    agent_result = _mock_db_result(None)
    db.execute.side_effect = [team_result, agent_result]

    data = AgentLinkCreate(
        from_agent_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
        link_type=LinkType.handoff,
    )
    with pytest.raises(AgentNotInTeamError):
        await create_link(db, team_id, data)


@pytest.mark.asyncio
async def test_create_link_to_agent_not_in_team():
    db = _make_db()
    team_id = uuid.uuid4()
    from_agent_id = uuid.uuid4()
    to_agent_id = uuid.uuid4()
    # team exists → ok, from_agent → ok, to_agent → not found
    db.execute.side_effect = [
        _mock_db_result(team_id),
        _mock_db_result(from_agent_id),
        _mock_db_result(None),
    ]

    data = AgentLinkCreate(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        link_type=LinkType.review,
    )
    with pytest.raises(AgentNotInTeamError):
        await create_link(db, team_id, data)


@pytest.mark.asyncio
async def test_create_link_duplicate():
    db = _make_db()
    team_id = uuid.uuid4()
    from_agent_id = uuid.uuid4()
    to_agent_id = uuid.uuid4()
    # team exists, from_agent exists, to_agent exists
    db.execute.side_effect = [
        _mock_db_result(team_id),
        _mock_db_result(from_agent_id),
        _mock_db_result(to_agent_id),
    ]
    db.commit.side_effect = IntegrityError("dup", {}, None)

    data = AgentLinkCreate(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        link_type=LinkType.handoff,
    )
    with pytest.raises(DuplicateLinkError):
        await create_link(db, team_id, data)
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_link_success():
    db = _make_db()
    team_id = uuid.uuid4()
    from_agent_id = uuid.uuid4()
    to_agent_id = uuid.uuid4()
    db.execute.side_effect = [
        _mock_db_result(team_id),
        _mock_db_result(from_agent_id),
        _mock_db_result(to_agent_id),
    ]

    data = AgentLinkCreate(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        link_type=LinkType.migration_brief,
    )
    result = await create_link(db, team_id, data)
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()
    assert result is not None


@pytest.mark.asyncio
async def test_delete_link_not_found():
    db = _make_db()
    db.execute.return_value = _mock_db_result(None)
    with pytest.raises(LinkNotFoundError):
        await delete_link(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_link_success():
    db = _make_db()
    fake_link = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake_link
    db.execute.return_value = result_mock

    await delete_link(db, uuid.uuid4())
    db.delete.assert_awaited_once_with(fake_link)
    db.commit.assert_awaited_once()

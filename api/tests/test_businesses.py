import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

SERVICE = "app.routers.businesses"


def make_business(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "name": "Acme Corp",
        "description": "A test business",
        "created_at": datetime(2024, 1, 1),
        "products_count": 0,
    }
    defaults.update(kwargs)
    return defaults


@pytest.mark.asyncio
async def test_list_businesses(client):
    biz = make_business()
    with patch(f"{SERVICE}.get_businesses", new_callable=AsyncMock, return_value=[biz]):
        resp = await client.get("/api/businesses")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_create_business(client):
    biz = make_business()
    with patch(f"{SERVICE}.create_business", new_callable=AsyncMock, return_value=biz):
        resp = await client.post("/api/businesses", json={"name": "Acme Corp"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_get_business(client):
    biz = make_business()
    bid = biz["id"]
    with patch(f"{SERVICE}.get_business", new_callable=AsyncMock, return_value=biz):
        resp = await client.get(f"/api/businesses/{bid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_update_business(client):
    biz = make_business(name="Updated")
    bid = biz["id"]
    with patch(f"{SERVICE}.update_business", new_callable=AsyncMock, return_value=biz):
        resp = await client.put(f"/api/businesses/{bid}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_business_no_force(client):
    bid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_business", new_callable=AsyncMock, return_value=None):
        resp = await client.delete(f"/api/businesses/{bid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_business_force(client):
    bid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_business", new_callable=AsyncMock, return_value=None):
        resp = await client.delete(f"/api/businesses/{bid}?force=true")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_business_with_products_no_force(client):
    bid = uuid.uuid4()
    exc = HTTPException(status_code=409, detail={"products_count": 2})
    with patch(f"{SERVICE}.delete_business", new_callable=AsyncMock, side_effect=exc):
        resp = await client.delete(f"/api/businesses/{bid}")
    assert resp.status_code == 409
    assert resp.json()["detail"]["products_count"] == 2

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

SERVICE = "app.routers.products"


def make_product(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "business_id": uuid.uuid4(),
        "name": "My Product",
        "description": None,
        "git_url": None,
        "workspace_path": "/workspace/products/abc",
        "status": "pending",
        "clone_error": None,
        "created_at": datetime(2024, 1, 1),
    }
    defaults.update(kwargs)
    return defaults


@pytest.mark.asyncio
async def test_list_products(client):
    product = make_product()
    bid = product["business_id"]
    with patch(f"{SERVICE}.get_products", new_callable=AsyncMock, return_value=[product]):
        resp = await client.get(f"/api/businesses/{bid}/products")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_create_product(client):
    product = make_product()
    bid = product["business_id"]
    with patch(f"{SERVICE}.create_product", new_callable=AsyncMock, return_value=product):
        resp = await client.post(
            f"/api/businesses/{bid}/products",
            json={"name": "My Product", "business_id": str(bid)},
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "My Product"


@pytest.mark.asyncio
async def test_get_product(client):
    product = make_product()
    pid = product["id"]
    with patch(f"{SERVICE}.get_product", new_callable=AsyncMock, return_value=product):
        resp = await client.get(f"/api/products/{pid}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_product(client):
    product = make_product(name="Updated")
    pid = product["id"]
    with patch(f"{SERVICE}.update_product", new_callable=AsyncMock, return_value=product):
        resp = await client.put(f"/api/products/{pid}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_product(client):
    pid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_product", new_callable=AsyncMock, return_value=None):
        resp = await client.delete(f"/api/products/{pid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_clone_product(client):
    product = make_product(status="cloning", git_url="https://github.com/example/repo")
    pid = product["id"]
    with patch(f"{SERVICE}.clone_product", new_callable=AsyncMock, return_value=product):
        resp = await client.post(f"/api/products/{pid}/clone")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cloning"


@pytest.mark.asyncio
async def test_clone_product_no_git_url(client):
    pid = uuid.uuid4()
    exc = HTTPException(status_code=400, detail="Product has no git_url")
    with patch(f"{SERVICE}.clone_product", new_callable=AsyncMock, side_effect=exc):
        resp = await client.post(f"/api/products/{pid}/clone")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_clone_product_already_cloning(client):
    pid = uuid.uuid4()
    exc = HTTPException(status_code=409, detail="Product is already being cloned")
    with patch(f"{SERVICE}.clone_product", new_callable=AsyncMock, side_effect=exc):
        resp = await client.post(f"/api/products/{pid}/clone")
    assert resp.status_code == 409

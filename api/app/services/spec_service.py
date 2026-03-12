import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spec import Spec, SpecVersion
from app.schemas.spec import SpecCreate, SpecUpdate


async def create_spec(
    db: AsyncSession, product_id: uuid.UUID, data: SpecCreate
) -> Spec:
    spec = Spec(
        product_id=product_id,
        feature=data.feature,
        title=data.title,
        content=data.content,
        status=data.status,
        version=1,
    )
    db.add(spec)
    await db.flush()

    version = SpecVersion(
        spec_id=spec.id,
        version=1,
        content=data.content,
        author="user",
        summary="Initial version",
    )
    db.add(version)
    await db.commit()
    await db.refresh(spec)
    return spec


async def get_specs(
    db: AsyncSession, product_id: uuid.UUID
) -> list[Spec]:
    result = await db.execute(
        select(Spec)
        .where(Spec.product_id == product_id)
        .order_by(Spec.created_at)
    )
    return list(result.scalars().all())


async def get_spec(db: AsyncSession, spec_id: uuid.UUID) -> Spec:
    result = await db.execute(select(Spec).where(Spec.id == spec_id))
    spec = result.scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    return spec


async def update_spec(
    db: AsyncSession, spec_id: uuid.UUID, data: SpecUpdate
) -> Spec:
    spec = await get_spec(db, spec_id)

    content_changed = data.content is not None and data.content != spec.content

    if data.feature is not None:
        spec.feature = data.feature
    if data.title is not None:
        spec.title = data.title
    if data.content is not None:
        spec.content = data.content
    if data.status is not None:
        spec.status = data.status

    if content_changed:
        spec.version += 1
        version = SpecVersion(
            spec_id=spec.id,
            version=spec.version,
            content=data.content,
            author=data.author,
            summary=data.summary,
        )
        db.add(version)

    await db.commit()
    await db.refresh(spec)
    return spec


async def delete_spec(db: AsyncSession, spec_id: uuid.UUID) -> None:
    spec = await get_spec(db, spec_id)
    await db.delete(spec)
    await db.commit()


async def get_spec_versions(
    db: AsyncSession, spec_id: uuid.UUID
) -> list[SpecVersion]:
    await get_spec(db, spec_id)
    result = await db.execute(
        select(SpecVersion)
        .where(SpecVersion.spec_id == spec_id)
        .order_by(SpecVersion.version.desc())
    )
    return list(result.scalars().all())


async def rollback_spec(
    db: AsyncSession, spec_id: uuid.UUID, target_version: int
) -> Spec:
    spec = await get_spec(db, spec_id)

    result = await db.execute(
        select(SpecVersion).where(
            SpecVersion.spec_id == spec_id,
            SpecVersion.version == target_version,
        )
    )
    old_version = result.scalar_one_or_none()
    if not old_version:
        raise HTTPException(
            status_code=404, detail=f"Version {target_version} not found"
        )

    spec.version += 1
    spec.content = old_version.content

    new_version = SpecVersion(
        spec_id=spec.id,
        version=spec.version,
        content=old_version.content,
        author="user",
        summary=f"Rollback to v{target_version}",
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(spec)
    return spec

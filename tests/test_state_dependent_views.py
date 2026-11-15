"""State-dependent view tests for docuflow."""

from __future__ import annotations

import pytest
from src.docuflow import service


@pytest.mark.asyncio
async def test_templates_empty_vs_populated(db):
    assert await service.get_active_templates(db) == []

    await service.create_template(db, name="T1", category="general", body="Hello {{name}}")
    templates = await service.get_active_templates(db)
    assert len(templates) == 1
    assert templates[0]["name"] == "T1"


@pytest.mark.asyncio
async def test_template_missing_vs_present(db):
    assert await service.get_template(db, 99999) is None

    tid = await service.create_template(db, name="T1", category="general", body="body")
    t = await service.get_template(db, tid)
    assert t is not None
    assert t["name"] == "T1"


@pytest.mark.asyncio
async def test_documents_empty_vs_populated(db):
    await service.ensure_user(db, user_id=1, name="U")
    assert await service.get_user_documents(db, 1) == []

    tid = await service.create_template(db, name="T1", category="general", body="body")
    await service.save_document(db, user_id=1, template_id=tid, template_version=1, field_values="{}")
    docs = await service.get_user_documents(db, 1)
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_document_missing_vs_present(db):
    assert await service.get_document(db, 99999) is None

    await service.ensure_user(db, user_id=1, name="U")
    tid = await service.create_template(db, name="T1", category="general", body="body")
    doc_id = await service.save_document(db, user_id=1, template_id=tid, template_version=1, field_values="{}")
    doc = await service.get_document(db, doc_id)
    assert doc is not None


@pytest.mark.asyncio
async def test_subscription_none_vs_present(db):
    assert await service.get_user_subscription(db, user_id=1) is None

    await service.ensure_user(db, user_id=1, name="U")
    # create subscription manually
    async with db.transaction() as session:
        from sqlalchemy import text

        await session.execute(
            text(
                "INSERT INTO subscriptions (user_id, plan, docs_limit, docs_used, status) "
                "VALUES (1, 'free', 5, 0, 'active')"
            )
        )
    sub = await service.get_user_subscription(db, user_id=1)
    assert sub is not None
    assert sub["plan"] == "free"


@pytest.mark.asyncio
async def test_template_count_empty_vs_populated(db):
    assert await service.get_template_count(db) == 0
    await service.create_template(db, name="T1", category="general", body="body")
    assert await service.get_template_count(db) == 1

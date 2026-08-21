from __future__ import annotations

import pytest

from src.docuflow import service


@pytest.mark.asyncio
async def test_ensure_user(db):
    await service.ensure_user(db, 123, "Test", "testuser")
    count = await service.get_user_count(db)
    assert count == 1


@pytest.mark.asyncio
async def test_ensure_user_idempotent(db):
    await service.ensure_user(db, 123, "Test", "testuser")
    await service.ensure_user(db, 123, "Test2", "testuser2")
    count = await service.get_user_count(db)
    assert count == 1


@pytest.mark.asyncio
async def test_create_template(db):
    tpl_id = await service.create_template(
        db, name="Договор", category="юридические", body="Текст {{party}}"
    )
    assert tpl_id > 0


@pytest.mark.asyncio
async def test_get_active_templates(db):
    await service.create_template(
        db, name="Договор", category="юридические", body="Текст"
    )
    templates = await service.get_active_templates(db)
    assert len(templates) == 1


@pytest.mark.asyncio
async def test_get_active_templates_by_category(db):
    await service.create_template(
        db, name="Договор", category="юридические", body="Текст"
    )
    await service.create_template(
        db, name="Счёт", category="бухгалтерия", body="Сумма {{amount}}"
    )
    templates = await service.get_active_templates(db, category="юридические")
    assert len(templates) == 1


@pytest.mark.asyncio
async def test_add_template_field(db):
    tpl_id = await service.create_template(
        db, name="Договор", category="юридические", body="Текст {{party}}"
    )
    field_id = await service.add_template_field(
        db, template_id=tpl_id, name="party", label="Сторона",
        field_type="text", required=True, example="ООО Ромашка"
    )
    assert field_id > 0


@pytest.mark.asyncio
async def test_get_template_fields(db):
    tpl_id = await service.create_template(
        db, name="Договор", category="юридические", body="Текст {{party}}"
    )
    await service.add_template_field(
        db, template_id=tpl_id, name="party", label="Сторона"
    )
    fields = await service.get_template_fields(db, tpl_id)
    assert len(fields) == 1


@pytest.mark.asyncio
async def test_save_document(db):
    await service.ensure_user(db, 123, "Test", "testuser")
    tpl_id = await service.create_template(
        db, name="Договор", category="юридические", body="Текст"
    )
    doc_id = await service.save_document(
        db, user_id=123, template_id=tpl_id, template_version=1,
        field_values={"party": "ООО Ромашка"}
    )
    assert doc_id > 0


@pytest.mark.asyncio
async def test_get_user_documents(db):
    await service.ensure_user(db, 123, "Test", "testuser")
    tpl_id = await service.create_template(
        db, name="Договор", category="юридические", body="Текст"
    )
    await service.save_document(
        db, user_id=123, template_id=tpl_id, template_version=1,
        field_values={"party": "ООО Ромашка"}
    )
    docs = await service.get_user_documents(db, 123)
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_get_categories(db):
    await service.create_template(
        db, name="Договор", category="юридические", body="Текст"
    )
    await service.create_template(
        db, name="Счёт", category="бухгалтерия", body="Сумма"
    )
    categories = await service.get_categories(db)
    assert len(categories) == 2


@pytest.mark.asyncio
async def test_get_template_count(db):
    await service.create_template(
        db, name="Договор", category="юридические", body="Текст"
    )
    count = await service.get_template_count(db)
    assert count == 1


@pytest.mark.asyncio
async def test_get_document_count(db):
    await service.ensure_user(db, 123, "Test", "testuser")
    tpl_id = await service.create_template(
        db, name="Договор", category="юридические", body="Текст"
    )
    await service.save_document(
        db, user_id=123, template_id=tpl_id, template_version=1,
        field_values={}
    )
    count = await service.get_document_count(db)
    assert count == 1

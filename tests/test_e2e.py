from __future__ import annotations

import pytest

from src.docuflow import service
from src.generator.parser import parse_template_fields, substitute_template
from src.generator.pdf import render_pdf


@pytest.mark.asyncio
async def test_full_document_generation_flow(db):
    await service.ensure_user(db, 111, "Test", "testuser")
    tpl_id = await service.create_template(
        db, name="Договор", category="юридические",
        body="Договор между {{party_a}} и {{party_b}}"
    )
    await service.add_template_field(
        db, template_id=tpl_id, name="party_a", label="Сторона А",
        field_type="text", required=True, example="ООО Ромашка"
    )
    await service.add_template_field(
        db, template_id=tpl_id, name="party_b", label="Сторона Б",
        field_type="text", required=True, example="ИП Иванов"
    )

    fields = await service.get_template_fields(db, tpl_id)
    assert len(fields) == 2

    body = (await service.get_template(db, tpl_id))["body"]
    rendered = substitute_template(body, {"party_a": "ООО Ромашка", "party_b": "ИП Иванов"})
    assert "ООО Ромашка" in rendered
    assert "ИП Иванов" in rendered

    doc_id = await service.save_document(
        db, user_id=111, template_id=tpl_id, template_version=1,
        field_values={"party_a": "ООО Ромашка", "party_b": "ИП Иванов"}
    )
    assert doc_id > 0

    docs = await service.get_user_documents(db, 111)
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_pdf_render():
    import tempfile
    from pathlib import Path
    text = "Договор\nСторона А: ООО Ромашка\nСторона Б: ИП Иванов"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    render_pdf(text, path)
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


@pytest.mark.asyncio
async def test_template_fields_parsing():
    body = "Договор между {{party_a}} и {{party_b}}, сумма {{amount}} руб."
    fields = parse_template_fields(body)
    assert len(fields) == 3
    assert "party_a" in fields
    assert "party_b" in fields
    assert "amount" in fields

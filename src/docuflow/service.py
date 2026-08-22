from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from src.core.database import Database


async def ensure_user(db: Database, user_id: int, name: str | None = None, username: str | None = None) -> None:
    async with db.transaction() as session:
        await session.execute(
            text(
                "INSERT OR IGNORE INTO users (user_id, name, username) VALUES (:uid, :name, :uname)"
            ),
            {"uid": user_id, "name": name, "uname": username},
        )


async def get_active_templates(db: Database, category: str | None = None) -> list[dict[str, Any]]:
    async with db.session() as session:
        if category:
            result = await session.execute(
                text("SELECT * FROM templates WHERE is_active = 1 AND category = :cat ORDER BY name"),
                {"cat": category},
            )
        else:
            result = await session.execute(
                text("SELECT * FROM templates WHERE is_active = 1 ORDER BY name")
            )
        return [dict(r) for r in result.mappings().all()]


async def get_template(db: Database, template_id: int) -> dict[str, Any] | None:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM templates WHERE id = :id"), {"id": template_id}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def get_template_fields(db: Database, template_id: int) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM template_fields WHERE template_id = :tid ORDER BY field_order"
            ),
            {"tid": template_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def create_template(
    db: Database, *, name: str, category: str, body: str
) -> int:
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "INSERT INTO templates (name, category, body) VALUES (:name, :cat, :body)"
            ),
            {"name": name, "cat": category, "body": body},
        )
        tpl_id = result.lastrowid  # type: ignore[attr-defined]
        assert tpl_id is not None
        return int(tpl_id)


async def add_template_field(
    db: Database,
    *,
    template_id: int,
    name: str,
    label: str,
    field_type: str = "text",
    required: bool = True,
    example: str | None = None,
    options: str | None = None,
    field_order: int = 0,
) -> int:
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "INSERT INTO template_fields "
                "(template_id, name, label, field_type, required, example, options, field_order) "
                "VALUES (:tid, :name, :label, :type, :req, :ex, :opts, :order)"
            ),
            {
                "tid": template_id,
                "name": name,
                "label": label,
                "type": field_type,
                "req": int(required),
                "ex": example,
                "opts": options,
                "order": field_order,
            },
        )
        field_id = result.lastrowid  # type: ignore[attr-defined]
        assert field_id is not None
        return int(field_id)


async def save_document(
    db: Database,
    *,
    user_id: int,
    template_id: int,
    template_version: int,
    field_values: dict[str, Any],
    file_path: str | None = None,
) -> int:
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "INSERT INTO documents (user_id, template_id, template_version, field_values, file_path) "
                "VALUES (:uid, :tid, :ver, :fv, :fp)"
            ),
            {
                "uid": user_id,
                "tid": template_id,
                "ver": template_version,
                "fv": json.dumps(field_values),
                "fp": file_path,
            },
        )
        doc_id = result.lastrowid  # type: ignore[attr-defined]
        assert doc_id is not None
        return int(doc_id)


async def get_user_documents(db: Database, user_id: int) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT d.*, t.name as template_name FROM documents d "
                "JOIN templates t ON d.template_id = t.id "
                "WHERE d.user_id = :uid ORDER BY d.created_at DESC LIMIT 20"
            ),
            {"uid": user_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_document(db: Database, doc_id: int) -> dict[str, Any] | None:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM documents WHERE id = :id"), {"id": doc_id}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def get_user_subscription(db: Database, user_id: int) -> dict[str, Any] | None:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM subscriptions WHERE user_id = :uid"), {"uid": user_id}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def increment_docs_used(db: Database, user_id: int) -> None:
    async with db.transaction() as session:
        await session.execute(
            text(
                "UPDATE subscriptions SET docs_used = docs_used + 1 WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )


async def get_categories(db: Database) -> list[str]:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT DISTINCT category FROM templates WHERE is_active = 1 ORDER BY category")
        )
        return [str(r[0]) for r in result.all()]


async def get_template_count(db: Database) -> int:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM templates WHERE is_active = 1")
        )
        row = result.fetchone()
        return int(row[0]) if row else 0


async def get_document_count(db: Database) -> int:
    async with db.session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM documents"))
        row = result.fetchone()
        return int(row[0]) if row else 0


async def get_user_count(db: Database) -> int:
    async with db.session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        row = result.fetchone()
        return int(row[0]) if row else 0


async def add_quota(db: Database, user_id: int, docs: int) -> bool:
    """Add docs to the subscription limit after successful payment."""
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "UPDATE subscriptions SET docs_limit = docs_limit + :docs"
                " WHERE user_id = :uid"
            ),
            {"docs": docs, "uid": user_id},
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]


async def record_payment(
    db: Database, user_id: int, provider: str, amount: float, external_id: str | None
) -> None:
    async with db.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO payments (user_id, provider, amount, status, external_id)"
                " VALUES (:uid, :provider, :amount, 'paid', :ext)"
            ),
            {"uid": user_id, "provider": provider, "amount": amount, "ext": external_id},
        )

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from src.core.config import Config
from src.core.database import Database
from src.core.migrations import migrate as run_migrate
from src.docuflow import service


@pytest.fixture
async def db(tmp_path: Any) -> Database:
    cfg = Config(bot_token="", db_path=str(tmp_path / "test.db"))
    database = Database(cfg)
    await run_migrate(database)
    yield database
    await database.close()


async def _seed_user(db: Database, uid: int = 42) -> None:
    async with db.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO subscriptions (user_id, plan, docs_limit, docs_used)"
                " VALUES (:uid, 'free', 5, 0)"
            ),
            {"uid": uid},
        )


async def test_add_quota_increments_limit(db: Database) -> None:
    await _seed_user(db)
    ok = await service.add_quota(db, 42, docs=10)
    assert ok is True
    sub = await service.get_user_subscription(db, 42)
    assert sub is not None
    assert sub["docs_limit"] == 15


async def test_add_quota_unknown_user_returns_false(db: Database) -> None:
    assert await service.add_quota(db, 999, docs=10) is False


async def test_record_payment_inserts_paid_row(db: Database) -> None:
    await _seed_user(db)
    await service.record_payment(db, 42, "stars", 10.0, "chg_123")
    async with db.session() as session:
        row = (await session.execute(text("SELECT provider, amount, status FROM payments"))).first()
    assert row is not None
    assert tuple(row) == ("stars", 10.0, "paid")

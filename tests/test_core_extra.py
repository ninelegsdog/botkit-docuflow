from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.state import State
from aiogram.types import (
    Chat,
    Message,
    PreCheckoutQuery,
    SuccessfulPayment,
    Update,
    User,
)
from src.core.auth import AuthMiddleware
from src.core.bot_factory import AppState, create_app
from src.core.config import Config
from src.core.errors import (
    RetryMiddleware,
    default_error_handler,
    register_error_handler,
)
from src.core.fsm import AdminAuth, DocGenerate, TemplateCreate
from src.core.metrics import Metrics, UpdatesMiddleware, create_metrics_app
from src.core.nav import admin_menu, client_menu
from src.core.sentry import init_sentry
from src.core.storage import Storage
from src.core.throttling import ThrottlingMiddleware
from src.core.ui import escape, template_card
from src.core.webhook import create_app as create_webhook_app


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def test_config_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAfake")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("ADMIN_IDS", "1,2,3")
    monkeypatch.setenv("FREE_DOCS_LIMIT", "9")
    cfg = Config.from_env()
    assert cfg.bot_token == "123456789:AAfake"
    assert cfg.admin_password == "secret"
    assert cfg.admin_ids == [1, 2, 3]
    assert cfg.free_docs_limit == 9


def test_config_validate_ok():
    cfg = Config(bot_token="x", admin_password="y", admin_ids=[1])
    cfg.validate()  # must not raise


@pytest.mark.parametrize("field", ["bot_token", "admin_password", "admin_ids"])
def test_config_validate_missing(field):
    kwargs = dict(bot_token="x", admin_password="y", admin_ids=[1])
    kwargs[field] = "" if field != "admin_ids" else []
    cfg = Config(**kwargs)
    with pytest.raises(RuntimeError):
        cfg.validate()


# --------------------------------------------------------------------------- #
# bot_factory / app
# --------------------------------------------------------------------------- #
def _make_state() -> AppState:
    with patch("src.core.bot_factory.RedisStorage.from_url", return_value=MagicMock()):
        return create_app(Config(bot_token="123456789:AAfake", admin_password="s", admin_ids=[1]))


def test_create_app_builds_state():
    state = _make_state()
    assert isinstance(state.bot, Bot)
    assert isinstance(state.dp, Dispatcher)
    assert state.config.bot_token == "123456789:AAfake"


def test_register_routers():
    from src.app import register_routers

    state = _make_state()
    register_routers(state)  # must not raise
    assert len(state.dp.sub_routers) >= 2


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #
async def test_retry_middleware_retries():
    from aiogram.exceptions import TelegramRetryAfter

    mw = RetryMiddleware(max_retries=3, delay=0)
    handler = AsyncMock(side_effect=[TelegramRetryAfter(None, "r", 0), "ok"])
    assert await mw(handler, MagicMock(), {}) == "ok"
    assert handler.await_count == 2


async def test_retry_middleware_network():
    from aiogram.exceptions import TelegramNetworkError

    mw = RetryMiddleware(max_retries=2, delay=0)
    handler = AsyncMock(side_effect=TelegramNetworkError(None, "n"))
    with pytest.raises(TelegramNetworkError):
        await mw(handler, MagicMock(), {})
    assert handler.await_count == 2


async def test_default_error_handler_retry_after():
    from aiogram.exceptions import TelegramRetryAfter

    await default_error_handler(MagicMock(), TelegramRetryAfter(None, "r", 0))


async def test_default_error_handler_network():
    from aiogram.exceptions import TelegramNetworkError

    await default_error_handler(MagicMock(), TelegramNetworkError(None, "n"))


async def test_default_error_handler_unhandled(caplog):
    await default_error_handler(MagicMock(), RuntimeError("boom"))


def test_register_error_handler():
    from types import SimpleNamespace

    fake_dp = SimpleNamespace(error=MagicMock(return_value=MagicMock()))
    register_error_handler(fake_dp)  # must not raise


# --------------------------------------------------------------------------- #
# storage (SQL-backed Storage)
# --------------------------------------------------------------------------- #
def _fake_db():
    db = MagicMock()
    sess = AsyncMock()
    sess.execute = AsyncMock()
    sess.execute.return_value.fetchone = MagicMock(return_value=(1,))
    cm = AsyncMock()
    cm.__aenter__.return_value = sess
    cm.__aexit__.return_value = False
    db.session = MagicMock(return_value=cm)
    db.transaction = MagicMock(return_value=cm)
    return db


async def test_storage_get_setting():
    storage = Storage(_fake_db())
    assert await storage.get_setting("theme") == "1"


async def test_storage_set_setting():
    db = _fake_db()
    storage = Storage(db)
    await storage.set_setting("theme", "dark")
    db.transaction.assert_called()


# --------------------------------------------------------------------------- #
# throttling (in-memory)
# --------------------------------------------------------------------------- #
async def test_throttle_allows_then_blocks():
    mw = ThrottlingMiddleware(min_interval=1.0)
    handler = AsyncMock()
    msg = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=7, is_bot=False, first_name="U"),
        text="hi",
    )
    assert await mw(handler, msg, {}) is not None
    assert await mw(handler, msg, {}) is None
    assert handler.await_count == 1


# --------------------------------------------------------------------------- #
# webhook
# --------------------------------------------------------------------------- #
def test_webhook_app_routes():
    state = _make_state()
    app = create_webhook_app(state)
    paths = [r.resource.canonical for r in app.router.routes() if r.resource]
    assert "/health" in paths
    assert "/metrics" in paths


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def test_metrics_counters():
    m = Metrics()
    m.inc_messages()
    m.inc_documents()
    m.inc_errors()
    assert m.messages_processed == 1
    assert m.documents_generated == 1
    assert m.errors == 1
    assert m.uptime_seconds() >= 0


async def test_updates_middleware():
    handler = AsyncMock()
    event = MagicMock()
    event.__class__.__name__ = "Message"
    await UpdatesMiddleware()(handler, event, {})
    assert handler.await_count == 1


def test_create_metrics_app():
    app = create_metrics_app()
    paths = [r.resource.canonical for r in app.router.routes() if r.resource]
    assert "/health" in paths
    assert "/metrics" in paths


# --------------------------------------------------------------------------- #
# sentry
# --------------------------------------------------------------------------- #
def test_init_sentry_empty():
    assert init_sentry("") is None


def test_init_sentry_missing_sdk():
    with patch.dict("sys.modules", {"sentry_sdk": None}):
        init_sentry("dsn")  # ImportError path must not raise


def test_init_sentry_with_sdk():
    fake = MagicMock()
    with patch.dict("sys.modules", {"sentry_sdk": fake}):
        init_sentry("https://abc@sentry.io/1")
        fake.init.assert_called_once_with(dsn="https://abc@sentry.io/1")


# --------------------------------------------------------------------------- #
# fsm / nav / ui
# --------------------------------------------------------------------------- #
def test_fsm_states():
    assert isinstance(TemplateCreate.entering_name, State)
    assert isinstance(DocGenerate.confirming, State)
    assert isinstance(AdminAuth.waiting_password, State)


def test_nav_menus():
    assert client_menu().keyboard
    assert admin_menu().keyboard


def test_ui_escape_and_card():
    assert escape(None) == ""
    assert escape("<a>") == "&lt;a&gt;"
    card = template_card({"name": "N", "category": "C"})
    assert "N" in card and "C" in card


# --------------------------------------------------------------------------- #
# auth middleware
# --------------------------------------------------------------------------- #
async def test_auth_middleware_injects_db():
    db = MagicMock()
    mw = AuthMiddleware(db)
    handler = AsyncMock()
    data: dict = {}
    await mw(handler, MagicMock(), data)
    assert data["db"] is db
    assert handler.await_count == 1


# --------------------------------------------------------------------------- #
# handlers (fb via real Bot + mocked make_request; db is a mock)
# --------------------------------------------------------------------------- #
def _feed_state():
    state = _make_state()
    state.db = _fake_db()
    from src.app import register_routers

    register_routers(state)
    return state


async def _feed(state, bot, update):
    with patch.object(bot.session, "make_request", new_callable=AsyncMock, return_value=AsyncMock(status=200)) as mr:
        await state.dp.feed_update(bot, update)
    return mr


def _msg(text, user_id=1):
    return Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="U"),
        text=text,
    )


async def test_docuflow_start():
    state = _feed_state()
    bot = Bot(token="123456789:AAfake")
    mr = await _feed(state, bot, Update(update_id=1, message=_msg("/start")))
    assert mr.await_count >= 1


async def test_docuflow_buy_docs():
    state = _feed_state()
    bot = Bot(token="123456789:AAfake")
    mr = await _feed(state, bot, Update(update_id=1, message=_msg("buy_docs_trigger")))
    # handler is Command("buy_docs"); feed a /buy_docs command text
    mr = await _feed(state, bot, Update(update_id=2, message=_msg("/buy_docs")))
    assert mr.await_count >= 1


async def test_docuflow_pre_checkout():
    state = _feed_state()
    bot = Bot(token="123456789:AAfake")
    query = PreCheckoutQuery(
        id="q1", from_user=User(id=1, is_bot=False, first_name="U"),
        currency="XTR", total_amount=10, invoice_payload="docs_pack_10",
    )
    mr = await _feed(state, bot, Update(update_id=1, pre_checkout_query=query))
    assert mr.await_count >= 1


async def test_docuflow_on_paid():
    state = _feed_state()
    bot = Bot(token="123456789:AAfake")
    sp = SuccessfulPayment(
        currency="XTR", total_amount=10, invoice_payload="docs_pack_10",
        telegram_payment_charge_id="chg1", provider_payment_charge_id="chg2",
    )
    msg = Message(
        message_id=1, date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="U"),
        successful_payment=sp,
    )
    mr = await _feed(state, bot, Update(update_id=1, message=msg))
    assert mr.await_count >= 1


async def test_admin_stats_admin():
    state = _feed_state()
    state.config.admin_ids = [1]
    bot = Bot(token="123456789:AAfake")
    mr = await _feed(state, bot, Update(update_id=1, message=_msg("📊 Статистика")))
    assert mr.await_count >= 1


async def test_admin_stats_not_admin():
    state = _feed_state()
    state.config.admin_ids = []
    bot = Bot(token="123456789:AAfake")
    mr = await _feed(state, bot, Update(update_id=1, message=_msg("📊 Статистика")))
    assert mr.await_count == 0


async def test_admin_limits_admin():
    state = _feed_state()
    state.config.admin_ids = [1]
    bot = Bot(token="123456789:AAfake")
    mr = await _feed(state, bot, Update(update_id=1, message=_msg("💳 Лимиты")))
    assert mr.await_count >= 1

from __future__ import annotations

import json

from aiohttp import web
from sqlalchemy import text

from src.core.bot_factory import AppState

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


async def health_handler(request: web.Request) -> web.Response:
    try:
        state: AppState = request.app["state"]
        async with state.db.session() as session:
            await session.execute(text("SELECT 1"))
        return web.Response(status=200, text="ok")
    except Exception:
        return web.Response(status=500, text="db unavailable")


async def metrics_handler(request: web.Request) -> web.Response:
    state: AppState = request.app["state"]
    m = state.metrics
    return web.json_response(
        {
            "messages": m.messages_processed,
            "documents": m.documents_generated,
            "errors": m.errors,
            "uptime": m.uptime_seconds(),
        }
    )


async def webhook_handler(request: web.Request) -> web.Response:
    """Accept a Telegram update, enforcing the secret-token header.

    Mirrors aiogram's `SimpleRequestHandler` contract: the
    `X-Telegram-Bot-Api-Secret-Token` header must equal `config.webhook_secret`.
    """
    state: AppState = request.app["state"]
    expected = state.config.webhook_secret
    secret = request.headers.get(SECRET_HEADER)
    if not expected or secret != expected:
        return web.Response(status=401, text="unauthorized")

    raw = await request.read()
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return web.Response(status=400, text="bad request")

    try:
        await state.dp.feed_raw_update(state.bot, payload)
    except Exception:
        return web.Response(status=400, text="invalid update")

    return web.Response(status=200, text="ok")


def create_app(state: AppState) -> web.Application:
    app = web.Application()
    app["state"] = state
    app.router.add_get("/health", health_handler)
    app.router.add_get("/metrics", metrics_handler)
    app.router.add_post("/webhook", webhook_handler)
    return app

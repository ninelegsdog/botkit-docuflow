"""docuflow's pre_checkout must not approve a forged amount.

`pre_checkout_query` is the only gate between the user and the charge. Answering
`ok=True` unconditionally means a hand-crafted update buys the 10-Star pack for 1 Star.
The handler now pins both the invoice payload and the amount.

`PreCheckoutQuery` is a frozen pydantic model, so the handler is called with a stand-in
that records what it answered instead of patching the real type.
"""
from __future__ import annotations

from typing import Any

import pytest
from src.core.bot_factory import AppState
from src.docuflow.handlers import create_docuflow_router


class RecordingQuery:
    """Stands in for PreCheckoutQuery - only the attributes the handler reads."""

    def __init__(self, payload: str, amount: int) -> None:
        self.invoice_payload = payload
        self.total_amount = amount
        self.answers: list[bool] = []

    async def answer(self, ok: bool, **kwargs: Any) -> None:
        self.answers.append(ok)


def _handler() -> Any:
    state = AppState.__new__(AppState)
    state.dp = None  # type: ignore[attr-defined]
    state.db = None  # type: ignore[attr-defined]
    state.config = None  # type: ignore[attr-defined]
    state.metrics = None  # type: ignore[attr-defined]
    router = create_docuflow_router(state)  # type: ignore[arg-type]
    return list(router.pre_checkout_query.handlers)[0].callback


@pytest.mark.asyncio
async def test_real_purchase_is_approved():
    """Sanity: the change must not break the normal path."""
    query = RecordingQuery("docs_pack_10", 10)
    await _handler()(query)
    assert query.answers == [True]


@pytest.mark.asyncio
async def test_forged_amount_is_refused():
    """Same product, one Star instead of ten - must not be approved."""
    query = RecordingQuery("docs_pack_10", 1)
    await _handler()(query)
    assert query.answers == [False]


@pytest.mark.asyncio
async def test_unknown_payload_is_refused():
    query = RecordingQuery("docs_pack_free", 0)
    await _handler()(query)
    assert query.answers == [False]

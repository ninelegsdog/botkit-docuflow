from __future__ import annotations

import html
from typing import Any


def escape(text: str | None) -> str:
    return html.escape(str(text)) if text else ""


def template_card(tpl: dict[str, Any]) -> str:
    return (
        f"📄 {escape(str(tpl.get('name', '')))}\n"
        f"📂 {escape(str(tpl.get('category', '')))} | v{tpl.get('version', 1)}"
    )

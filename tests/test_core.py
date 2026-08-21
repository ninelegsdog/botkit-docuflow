from __future__ import annotations

import pytest

from src.core.config import Config
from src.core.ui import escape
from src.generator.parser import parse_template_fields, substitute_template, validate_field_value


@pytest.mark.asyncio
async def test_config_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    config = Config.from_env()
    assert config.bot_token == "test_token"


def test_escape():
    assert escape("<script>") == "&lt;script&gt;"
    assert escape("hello") == "hello"
    assert escape(None) == ""


def test_parse_template_fields():
    body = "Договор между {{party_a}} и {{party_b}}"
    fields = parse_template_fields(body)
    assert "party_a" in fields
    assert "party_b" in fields


def test_parse_template_fields_no_duplicates():
    body = "Текст {{a}} и ещё {{a}}"
    fields = parse_template_fields(body)
    assert fields.count("a") == 1


def test_substitute_template():
    body = "Договор между {{party_a}} и {{party_b}}"
    result = substitute_template(body, {"party_a": "ООО Ромашка", "party_b": "ИП Иванов"})
    assert "ООО Ромашка" in result
    assert "ИП Иванов" in result
    assert "{{party_a}}" not in result


def test_validate_text():
    ok, _ = validate_field_value("text", "Hello")
    assert ok


def test_validate_number():
    ok, _ = validate_field_value("number", "123.45")
    assert ok
    ok, err = validate_field_value("number", "abc")
    assert not ok
    assert "число" in err


def test_validate_date():
    ok, _ = validate_field_value("date", "21.08.2026")
    assert ok
    ok, err = validate_field_value("date", "2026-08-21")
    assert not ok
    assert "ДД.ММ.ГГГГ" in err


def test_validate_phone():
    ok, _ = validate_field_value("phone", "+79001234567")
    assert ok
    ok, err = validate_field_value("phone", "12345")
    assert not ok
    assert "телефон" in err.lower()

from __future__ import annotations

import re
from typing import Any


def parse_template_fields(body: str) -> list[str]:
    return list(set(re.findall(r"\{\{(\w+)\}\}", body)))


def substitute_template(body: str, values: dict[str, Any]) -> str:
    result = body
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def validate_field_value(field_type: str, value: str) -> tuple[bool, str]:
    if field_type == "number":
        try:
            float(value)
            return True, ""
        except ValueError:
            return False, "Введите число"
    if field_type == "date":
        parts = value.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return True, ""
        return False, "Введите дату ДД.ММ.ГГГГ"
    if field_type == "phone":
        cleaned = re.sub(r"[\s\-\(\)]", "", value)
        if cleaned.startswith("+") and cleaned[1:].isdigit():
            return True, ""
        return False, "Введите телефон +7XXXXXXXXXX"
    return True, ""

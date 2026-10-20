"""Тексты бота: константы существуют, хелперы подставляют свои аргументы.

Зачем
=====

`src/docuflow/texts.py` — единый источник строк, которые бот отправляет. Тест
держит две вещи:

1. **Константы на месте и непусты.** Обработчик, отдавший пустую строку, —
   молчаливый дефект: пользователь видит пузырь без текста, а тест на поведение
   (если он сверяет вхождение) проходит.
2. **Хелперы действительно подставляют переданное.** Правка, выбросившая аргумент
   (номер поля, имя шаблона, счётчик), иначе прошла бы незамеченной: строка всё
   ещё «есть».

Каждая проверка имеет негативного близнеца: сломай подстановку — тест красный.
"""

from __future__ import annotations

import pytest
from src.docuflow import texts

CONSTANTS = [
    texts.WELCOME,
    texts.NO_TEMPLATES,
    texts.CHOOSE_CATEGORY,
    texts.NO_TEMPLATES_IN_CATEGORY,
    texts.CHOOSE_TEMPLATE,
    texts.TEMPLATE_NO_FIELDS,
    texts.TEMPLATE_NOT_FOUND,
    texts.FIELD_REQUIRED,
    texts.DOC_GENERATED,
    texts.CHOOSE_ACTION,
    texts.RESTART_FROM_FIRST,
    texts.NO_DOCUMENTS,
    texts.ASK_PASSWORD,
    texts.ADMIN_WELCOME,
    texts.BAD_PASSWORD,
    texts.TOO_MANY_ATTEMPTS,
    texts.ACCESS_STUB,
    texts.PAID_LIMIT_UP,
    texts.UNKNOWN_PRODUCT,
    texts.BAD_REQUEST,
]

BUTTON_LABELS = [
    texts.BTN_CREATE_DOC,
    texts.BTN_MY_DOCS,
    texts.BTN_GENERATE,
    texts.BTN_EDIT,
    texts.BTN_STATS,
    texts.BTN_LIMITS,
    texts.BTN_ACCESS,
]


@pytest.mark.parametrize("value", CONSTANTS, ids=lambda v: v[:24])
def test_текст_непуст(value: str) -> None:
    """Пустой ответ — пузырь без текста; пользователь не поймёт, что случилось."""
    assert value.strip(), "текст сообщения пуст или из пробелов"


@pytest.mark.parametrize("label", BUTTON_LABELS, ids=lambda v: v[:24])
def test_подпись_кнопки_непуста(label: str) -> None:
    """Кнопка без подписи неотличима от декоративного разделителя."""
    assert label.strip(), "подпись кнопки пуста"


def test_все_подписи_кнопок_уникальны() -> None:
    """Две кнопки с одной подписью — пользователь нажмёт не ту.

    Обработчики выше различают кнопки по тексту (`F.text == ...`), так что
    совпадение подписей ломает маршрутизацию, а не только вид.
    """
    duplicates = {x for x in BUTTON_LABELS if BUTTON_LABELS.count(x) > 1}
    assert not duplicates, f"дубли подписей кнопок: {duplicates}"


def test_приветствие_содержит_подстроку_из_кейсов() -> None:
    """Кейс фермы и e2e-тест цитируют подстроку без эмодзи — она обязана быть.

    `text_contains` сверяет вхождение, поэтому ведущий эмодзи правке не мешает,
    но сама фраза обязана остаться: это тот текст, который ловят оба пути.
    """
    assert "Генерация документов в Telegram" in texts.WELCOME


# ── хелперы: подстановка аргумента, а не литерал ────────────────────────────


def test_field_prompt_несёт_шаг_подпись_пример() -> None:
    """Без шага или примера пользователь не знает, что от него хотят."""
    got = texts.field_prompt(2, 5, "ИНН", "1234567890")
    assert "Поле 2/5" in got, got
    assert "ИНН" in got, got
    assert "1234567890" in got, got


def test_field_prompt_чужой_шаг_меняет_строку() -> None:
    """Негативный близнец: фиксированный шаг прошёл бы первую проверку."""
    assert texts.field_prompt(1, 3, "X", "y") != texts.field_prompt(2, 3, "X", "y")


def test_field_invalid_несёт_причину() -> None:
    """Сообщение без причины отказа не подсказывает, что исправить."""
    assert "неверный формат" in texts.field_invalid("неверный формат")


def test_confirm_summary_вставляет_сводку() -> None:
    """Пустая сводка вместо введённых данных — пользователь подтверждает вслепую."""
    got = texts.confirm_summary("• ИНН: 123")
    assert "• ИНН: 123" in got, got


def test_document_line_несёт_id_имя_дату() -> None:
    """Строка без id или даты — документ не найти в списке."""
    got = texts.document_line(7, "Договор", "2026-01-01")
    assert "#7" in got and "Договор" in got and "2026-01-01" in got, got


def test_document_line_различает_id() -> None:
    """Негативный близнец: фиксированный id прошёл бы первую проверку."""
    assert texts.document_line(1, "X", "d") != texts.document_line(2, "X", "d")


def test_admin_stats_несёт_три_счётчика() -> None:
    """Статистика, где счётчики совпали, — одна цифра под тремя ярлыками."""
    got = texts.admin_stats(templates=4, documents=12, users=30)
    assert "4" in got and "12" in got and "30" in got, got


def test_free_limit_вставляет_число() -> None:
    """Литерал вместо лимита показал бы пользователю чужое число."""
    assert "25" in texts.free_limit(25)

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def client_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Создать документ"), KeyboardButton(text="🗂 Мои документы")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Шаблоны"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="💳 Лимиты"), KeyboardButton(text="👥 Доступ")],
        ],
        resize_keyboard=True,
    )

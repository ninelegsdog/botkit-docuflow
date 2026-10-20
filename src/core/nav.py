from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from src.docuflow import texts


def client_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_CREATE_DOC), KeyboardButton(text=texts.BTN_MY_DOCS)],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_STATS)],
            [KeyboardButton(text=texts.BTN_LIMITS), KeyboardButton(text=texts.BTN_ACCESS)],
        ],
        resize_keyboard=True,
    )

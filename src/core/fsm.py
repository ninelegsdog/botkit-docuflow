from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class TemplateCreate(StatesGroup):
    entering_name = State()
    entering_category = State()
    entering_body = State()
    confirming = State()


class DocGenerate(StatesGroup):
    choosing_template = State()
    entering_fields = State()
    confirming = State()


class AdminAuth(StatesGroup):
    waiting_password = State()

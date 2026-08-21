from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.core.bot_factory import AppState
from src.core.fsm import AdminAuth
from src.core.nav import admin_menu, client_menu
from src.docuflow import service


def create_admin_router(state: AppState) -> Router:
    router = Router()
    db = state.db

    def is_admin(user_id: int) -> bool:
        return user_id == 123456789

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state_fsm: FSMContext) -> None:
        await state_fsm.set_state(AdminAuth.waiting_password)
        await message.answer("🔑 Введите пароль:")

    @router.message(AdminAuth.waiting_password)
    async def check_password(message: Message, state_fsm: FSMContext) -> None:
        if message.text == state.config.admin_password:
            await state_fsm.clear()
            await message.answer("✅ Добро пожаловать!", reply_markup=admin_menu())
        else:
            await state_fsm.clear()
            await message.answer("❌ Неверный пароль.", reply_markup=client_menu())

    @router.message(F.text == "📊 Статистика")
    async def admin_stats(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        tpl_count = await service.get_template_count(db)
        doc_count = await service.get_document_count(db)
        user_count = await service.get_user_count(db)
        await message.answer(
            f"📊 Статистика:\n"
            f"  Шаблонов: {tpl_count}\n"
            f"  Документов: {doc_count}\n"
            f"  Пользователей: {user_count}"
        )

    @router.message(F.text == "💳 Лимиты")
    async def admin_limits(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        await message.answer(f"💳 Бесплатный лимит: {state.config.free_docs_limit} документов/мес")

    @router.message(F.text == "👥 Доступ")
    async def admin_access(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        await message.answer("👥 Управление доступом (заглушка для v1)")

    return router

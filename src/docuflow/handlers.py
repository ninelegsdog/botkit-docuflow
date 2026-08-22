from __future__ import annotations

import tempfile

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from src.core.bot_factory import AppState
from src.core.fsm import DocGenerate
from src.core.nav import client_menu
from src.core.ui import escape
from src.docuflow import service
from src.generator.parser import substitute_template, validate_field_value
from src.generator.pdf import render_pdf


def create_docuflow_router(state: AppState) -> Router:
    router = Router()
    db = state.db

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        user_id = message.from_user.id  # type: ignore[union-attr]
        await service.ensure_user(
            db, user_id,
            getattr(message.from_user, "first_name", None),
            getattr(message.from_user, "username", None),
        )
        await message.answer(
            "📄 Генерация документов в Telegram!",
            reply_markup=client_menu(),
        )

    @router.message(F.text == "📄 Создать документ")
    async def start_create(message: Message, state_fsm: FSMContext) -> None:
        categories = await service.get_categories(db)
        if not categories:
            await message.answer("Нет доступных шаблонов.")
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=cat, callback_data=f"cat:{cat}")]
                for cat in categories
            ]
        )
        await message.answer("Выберите категорию:", reply_markup=kb)

    @router.callback_query(F.data.startswith("cat:"))
    async def choose_category(callback: CallbackQuery, state_fsm: FSMContext) -> None:
        if not callback.data:
            return
        category = callback.data.split(":", 1)[1]
        templates = await service.get_active_templates(db, category=category)
        if not templates:
            await callback.message.edit_text("Нет шаблонов в этой категории.")  # type: ignore[union-attr]
            await callback.answer()
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t["name"], callback_data=f"tpl:{t['id']}")]
                for t in templates
            ]
        )
        await callback.message.edit_text("Выберите шаблон:", reply_markup=kb)  # type: ignore[union-attr]
        await callback.answer()

    @router.callback_query(F.data.startswith("tpl:"))
    async def choose_template(callback: CallbackQuery, state_fsm: FSMContext) -> None:
        if not callback.data:
            return
        tpl_id = int(callback.data.split(":")[1])
        fields = await service.get_template_fields(db, tpl_id)
        if not fields:
            await callback.message.edit_text("Шаблон без полей.")  # type: ignore[union-attr]
            await callback.answer()
            return
        await state_fsm.update_data(template_id=tpl_id, fields=[f["name"] for f in fields],
                                     field_labels={f["name"]: f["label"] for f in fields},
                                     field_types={f["name"]: f["field_type"] for f in fields},
                                     field_examples={f["name"]: f.get("example", "") for f in fields},
                                     field_required={f["name"]: bool(f["required"]) for f in fields},
                                     values={}, current_field_idx=0)
        await state_fsm.set_state(DocGenerate.entering_fields)
        first_field = fields[0]
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"📝 Поле 1/{len(fields)}: {escape(first_field['label'])}\n"
            f"Пример: {escape(str(first_field.get('example', '')))}"
        )
        await callback.answer()

    @router.message(DocGenerate.entering_fields)
    async def enter_field(message: Message, state_fsm: FSMContext) -> None:
        data = await state_fsm.get_data()
        fields = data.get("fields", [])
        idx = data.get("current_field_idx", 0)
        field_types = data.get("field_types", {})
        field_required = data.get("field_required", {})
        values = data.get("values", {})

        if idx >= len(fields):
            return

        field_name = fields[idx]
        value = message.text or ""

        if not value and field_required.get(field_name, True):
            await message.answer("⚠️ Поле обязательное. Введите значение:")
            return

        if value:
            is_valid, error = validate_field_value(field_types.get(field_name, "text"), value)
            if not is_valid:
                await message.answer(f"⚠️ {error}. Попробуйте ещё раз:")
                return
            values[field_name] = value

        next_idx = idx + 1
        if next_idx >= len(fields):
            await state_fsm.update_data(values=values, current_field_idx=next_idx)
            summary = "\n".join(f"• {escape(str(data.get('field_labels', {}).get(k, k)))}: {escape(v)}"
                                for k, v in values.items())
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Сформировать", callback_data="doc_confirm"),
                        InlineKeyboardButton(text="✏️ Исправить", callback_data="doc_edit"),
                    ]
                ]
            )
            await state_fsm.set_state(DocGenerate.confirming)
            await message.answer(f"📋 Проверьте данные:\n{summary}", reply_markup=kb)
        else:
            next_field_name = fields[next_idx]
            labels = data.get("field_labels", {})
            examples = data.get("field_examples", {})
            await state_fsm.update_data(values=values, current_field_idx=next_idx)
            await message.answer(
                f"📝 Поле {next_idx + 1}/{len(fields)}: {escape(labels.get(next_field_name, next_field_name))}\n"
                f"Пример: {escape(str(examples.get(next_field_name, '')))}"
            )

    @router.callback_query(F.data == "doc_confirm", DocGenerate.confirming)
    async def confirm_generate(callback: CallbackQuery, state_fsm: FSMContext) -> None:
        data = await state_fsm.get_data()
        tpl_id = data.get("template_id", 0)
        values = data.get("values", {})

        template = await service.get_template(db, tpl_id)
        if not template:
            await callback.message.edit_text("❌ Шаблон не найден.")  # type: ignore[union-attr]
            await callback.answer()
            await state_fsm.clear()
            return

        body = str(template.get("body", ""))
        version = int(template.get("version", 1))
        rendered = substitute_template(body, values)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            file_path = f.name
        render_pdf(rendered, file_path)

        doc_id = await service.save_document(
            db,
            user_id=callback.from_user.id,
            template_id=tpl_id,
            template_version=version,
            field_values=values,
            file_path=file_path,
        )

        await callback.message.edit_text("✅ Документ сформирован!")  # type: ignore[union-attr]
        await callback.answer()
        await callback.message.answer_document(  # type: ignore[union-attr]
            FSInputFile(file_path),
            caption=f"📄 Документ #{doc_id}",
        )
        await callback.message.answer("Выберите действие:", reply_markup=client_menu())  # type: ignore[union-attr]
        await state_fsm.clear()

    @router.callback_query(F.data == "doc_edit")
    async def edit_fields(callback: CallbackQuery, state_fsm: FSMContext) -> None:
        await state_fsm.set_state(DocGenerate.entering_fields)
        await state_fsm.update_data(current_field_idx=0, values={})
        await callback.message.edit_text("✏️ Начнём заново. Поле 1:")  # type: ignore[union-attr]
        await callback.answer()

    @router.message(F.text == "🗂 Мои документы")
    async def my_documents(message: Message) -> None:
        docs = await service.get_user_documents(db, message.from_user.id)  # type: ignore[union-attr]
        if not docs:
            await message.answer("Нет документов.")
            return
        for doc in docs[:5]:
            await message.answer(
                f"📄 #{doc['id']} — {escape(str(doc.get('template_name', '')))} "
                f"({escape(str(doc.get('created_at', '')))})"
            )

    @router.message(Command("buy_docs"))
    async def buy_docs(message: Message) -> None:
        await message.answer_invoice(
            title="Документы",
            description="Пакет из 10 документов",
            payload="docs_pack_10",
            currency="XTR",
            prices=[LabeledPrice(label="10 документов", amount=10)],
        )

    @router.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery) -> None:
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def on_paid(message: Message) -> None:
        sp = message.successful_payment
        if sp is None or sp.invoice_payload != "docs_pack_10":
            return
        uid = message.from_user.id  # type: ignore[union-attr]
        ok = await service.add_quota(state.db, uid, docs=10)
        if ok:
            await service.record_payment(
                state.db, uid, "stars", float(sp.total_amount), sp.telegram_payment_charge_id
            )
        await message.answer("✅ Оплачено! Лимит увеличен на 10 документов.")

    return router

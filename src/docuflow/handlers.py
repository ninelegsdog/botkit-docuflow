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
from src.core.callbacks import parse_callback_int
from src.core.fsm import DocGenerate
from src.core.nav import client_menu
from src.core.ui import escape
from src.docuflow import service, texts
from src.generator.parser import substitute_template, validate_field_value
from src.generator.pdf import render_pdf


def create_docuflow_router(app_state: AppState) -> Router:
    router = Router()
    db = app_state.db

    @router.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        user_id = message.from_user.id  # type: ignore[union-attr]
        await service.ensure_user(
            db, user_id,
            getattr(message.from_user, "first_name", None),
            getattr(message.from_user, "username", None),
        )
        await message.answer(
            texts.WELCOME,
            reply_markup=client_menu(),
        )

    @router.message(F.text == "📄 Создать документ")
    async def start_create(message: Message, state: FSMContext) -> None:
        categories = await service.get_categories(db)
        if not categories:
            await message.answer(texts.NO_TEMPLATES)
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=cat, callback_data=f"cat:{cat}")]
                for cat in categories
            ]
        )
        await message.answer(texts.CHOOSE_CATEGORY, reply_markup=kb)

    @router.callback_query(F.data.startswith("cat:"))
    async def choose_category(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        category = callback.data.split(":", 1)[1]
        templates = await service.get_active_templates(db, category=category)
        if not templates:
            await callback.message.edit_text(texts.NO_TEMPLATES_IN_CATEGORY)  # type: ignore[union-attr]
            await callback.answer()
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t["name"], callback_data=f"tpl:{t['id']}")]
                for t in templates
            ]
        )
        await callback.message.edit_text(texts.CHOOSE_TEMPLATE, reply_markup=kb)  # type: ignore[union-attr]
        await callback.answer()

    @router.callback_query(F.data.startswith("tpl:"))
    async def choose_template(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        tpl_id = parse_callback_int(callback.data, "tpl:")
        if tpl_id is None:
            await callback.answer(texts.BAD_REQUEST, show_alert=True)
            return
        fields = await service.get_template_fields(db, tpl_id)
        if not fields:
            await callback.message.edit_text(texts.TEMPLATE_NO_FIELDS)  # type: ignore[union-attr]
            await callback.answer()
            return
        await state.update_data(template_id=tpl_id, fields=[f["name"] for f in fields],
                                     field_labels={f["name"]: f["label"] for f in fields},
                                     field_types={f["name"]: f["field_type"] for f in fields},
                                     field_examples={f["name"]: f.get("example", "") for f in fields},
                                     field_required={f["name"]: bool(f["required"]) for f in fields},
                                     values={}, current_field_idx=0)
        await state.set_state(DocGenerate.entering_fields)
        first_field = fields[0]
        await callback.message.edit_text(  # type: ignore[union-attr]
            texts.field_prompt(
                1,
                len(fields),
                escape(first_field["label"]),
                escape(str(first_field.get("example", ""))),
            )
        )
        await callback.answer()

    @router.message(DocGenerate.entering_fields)
    async def enter_field(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        fields = data.get("fields", [])
        idx = data.get("current_field_idx", 0)
        field_types = data.get("field_types", {})
        field_required = data.get("field_required", {})
        values = data.get("values", {})

        if idx >= len(fields):
            return

        field_name = fields[idx]
        value = (message.text or "").strip()

        if not value and field_required.get(field_name, True):
            await message.answer(texts.FIELD_REQUIRED)
            return

        if value:
            is_valid, error = validate_field_value(field_types.get(field_name, "text"), value)
            if not is_valid:
                await message.answer(texts.field_invalid(error))
                return
            values[field_name] = value

        next_idx = idx + 1
        if next_idx >= len(fields):
            await state.update_data(values=values, current_field_idx=next_idx)
            summary = "\n".join(f"• {escape(str(data.get('field_labels', {}).get(k, k)))}: {escape(v)}"
                                for k, v in values.items())
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text=texts.BTN_GENERATE, callback_data="doc_confirm"),
                        InlineKeyboardButton(text=texts.BTN_EDIT, callback_data="doc_edit"),
                    ]
                ]
            )
            await state.set_state(DocGenerate.confirming)
            await message.answer(texts.confirm_summary(summary), reply_markup=kb)
        else:
            next_field_name = fields[next_idx]
            labels = data.get("field_labels", {})
            examples = data.get("field_examples", {})
            await state.update_data(values=values, current_field_idx=next_idx)
            await message.answer(
                texts.field_prompt(
                    next_idx + 1,
                    len(fields),
                    escape(labels.get(next_field_name, next_field_name)),
                    escape(str(examples.get(next_field_name, ""))),
                )
            )

    @router.callback_query(F.data == "doc_confirm", DocGenerate.confirming)
    async def confirm_generate(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        tpl_id = data.get("template_id", 0)
        values = data.get("values", {})

        template = await service.get_template(db, tpl_id)
        if not template:
            await callback.message.edit_text(texts.TEMPLATE_NOT_FOUND)  # type: ignore[union-attr]
            await callback.answer()
            await state.clear()
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

        await callback.message.edit_text(texts.DOC_GENERATED)  # type: ignore[union-attr]
        await callback.answer()
        await callback.message.answer_document(  # type: ignore[union-attr]
            FSInputFile(file_path),
            caption=f"📄 Документ #{doc_id}",
        )
        await callback.message.answer(texts.CHOOSE_ACTION, reply_markup=client_menu())  # type: ignore[union-attr]
        await state.clear()

    @router.callback_query(F.data == "doc_edit")
    async def edit_fields(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(DocGenerate.entering_fields)
        await state.update_data(current_field_idx=0, values={})
        await callback.message.edit_text(texts.RESTART_FROM_FIRST)  # type: ignore[union-attr]
        await callback.answer()

    @router.message(F.text == "🗂 Мои документы")
    async def my_documents(message: Message) -> None:
        docs = await service.get_user_documents(db, message.from_user.id)  # type: ignore[union-attr]
        if not docs:
            await message.answer(texts.NO_DOCUMENTS)
            return
        for doc in docs[:5]:
            await message.answer(
                texts.document_line(
                    doc["id"],
                    escape(str(doc.get("template_name", ""))),
                    escape(str(doc.get("created_at", ""))),
                )
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
        # Validate before approving: pre_checkout is the only gate before the charge, so
        # an unconditional ok=True lets a hand-crafted update buy the pack for 1 Star
        # instead of 10. Both the payload and the amount are pinned to what we sell.
        if query.invoice_payload != "docs_pack_10" or int(query.total_amount) != 10:
            await query.answer(ok=False, error_message=texts.UNKNOWN_PRODUCT)
            return
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def on_paid(message: Message) -> None:
        sp = message.successful_payment
        if sp is None or sp.invoice_payload != "docs_pack_10":
            return
        uid = message.from_user.id  # type: ignore[union-attr]
        ok = await service.add_quota(app_state.db, uid, docs=10)
        if ok:
            await service.record_payment(
                app_state.db, uid, "stars", float(sp.total_amount), sp.telegram_payment_charge_id
            )
        await message.answer(texts.PAID_LIMIT_UP)

    return router

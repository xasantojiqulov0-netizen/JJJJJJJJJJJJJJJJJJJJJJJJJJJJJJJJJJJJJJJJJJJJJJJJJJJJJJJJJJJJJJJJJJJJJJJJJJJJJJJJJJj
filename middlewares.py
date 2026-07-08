from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database import SessionLocal, get_or_create_user, get_user


def make_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class DbSessionMiddleware(BaseMiddleware):
    """Har bir so'rovga async DB session ulaydi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with SessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


class SubscriptionMiddleware(BaseMiddleware):
    """
    Foydalanuvchi obunasini va blok statusini tekshiradi.
    Obunasi tugagan yoki bloklangan foydalanuvchilarga xabar yuboradi.
    Admin uchun bu filtr ishlamaydi.
    """

    # Bu callback/command'lar doim o'tadi — obuna tekshirilmaydi
    EXCLUDED_COMMANDS = {"/start", "/admin"}
    EXCLUDED_CALLBACKS = {
        "pay_menu", "tariff_", "cancel_payment", "send_receipt_",
        "back_main", "back_", "set_decoy", "edit_decoy_text",
        "reset_decoy",
    }

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from config import ADMIN_ID

        user_tg = None

        if isinstance(event, Message):
            user_tg = event.from_user
            text = event.text or ""
            if any(text.startswith(cmd) for cmd in self.EXCLUDED_COMMANDS):
                return await handler(event, data)

        elif isinstance(event, CallbackQuery):
            user_tg = event.from_user
            cb = event.data or ""
            if any(cb.startswith(prefix) for prefix in self.EXCLUDED_CALLBACKS):
                return await handler(event, data)
        else:
            return await handler(event, data)

        if user_tg is None:
            return await handler(event, data)

        # Admin filtrsiz o'tadi
        if user_tg.id == ADMIN_ID:
            return await handler(event, data)

        session = data.get("session")
        if session is None:
            return await handler(event, data)

        # FSM state'da bo'lsa o'tkazib yuboramiz (to'lov jarayoni)
        from aiogram.fsm.context import FSMContext
        fsm: FSMContext | None = data.get("state")
        if fsm is not None:
            current_state = await fsm.get_state()
            if current_state is not None:
                return await handler(event, data)

        db_user = await get_user(session, user_tg.id)
        if db_user is None:
            return await handler(event, data)

        # Bloklangan foydalanuvchi
        if db_user.is_blocked:
            block_text = "🚫 Hisobingiz bloklangan. Murojaat uchun admin bilan bog'laning."
            if isinstance(event, Message):
                await event.answer(block_text)
            elif isinstance(event, CallbackQuery):
                await event.answer(block_text, show_alert=True)
            return

        # Obuna tekshiruvi
        now = datetime.now(timezone.utc)
        sub_end = make_aware(db_user.subscription_end)
        if sub_end and sub_end > now:
            data["db_user"] = db_user
            return await handler(event, data)

        # Obunasi yo'q yoki tugagan
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Obuna sotib olish", callback_data="pay_menu")]
        ])
        text = (
            "🔴 <b>Obunangiz tugagan!</b>\n\n"
            "Botdan foydalanishni davom ettirish uchun obuna sotib oling.\n\n"
            "⬇️ Quyidagi tugmani bosing:"
        )
        if isinstance(event, Message):
            await event.answer(text, parse_mode="HTML", reply_markup=keyboard)
        elif isinstance(event, CallbackQuery):
            await event.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
            await event.answer()
        return

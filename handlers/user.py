from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import ADMIN_ID
from database import (
    get_or_create_user, get_user, get_active_card,
    Payment, User, TrapLog, get_trap_logs, get_trap_count,
    get_tariffs, get_tariff_by_id,
)
from keyboards import (
    main_menu_kb, tariffs_kb, payment_confirm_kb,
    cancel_kb, decoy_edit_kb,
)


DEFAULT_DECOY = "⏳ <b>Yuklanmoqda...</b>\n\nMa'lumotlar tayyorlanmoqda, biroz kuting."


def make_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


router = Router()


class PaymentState(StatesGroup):
    waiting_receipt = State()


class DecoyState(StatesGroup):
    waiting_message = State()


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()

    args = message.text.split()
    start_arg = args[1] if len(args) > 1 else None

    # ── TUZOQ: trap_<owner_id> ──────────────────────────────────────────────
    if start_arg and start_arg.startswith("trap_"):
        owner_id_str = start_arg[5:]
        if owner_id_str.isdigit():
            owner_id = int(owner_id_str)
            visitor = message.from_user

            if visitor.id != owner_id:
                # Bosuvchini ro'yxatdan o'tkazamiz
                await get_or_create_user(
                    session,
                    telegram_id=visitor.id,
                    full_name=visitor.full_name,
                    username=visitor.username,
                )

                # Egasini topamiz
                owner_result = await session.execute(
                    select(User).where(User.telegram_id == owner_id)
                )
                owner = owner_result.scalar_one_or_none()

                # TrapLog ga yozamiz
                log = TrapLog(
                    owner_id=owner_id,
                    visitor_id=visitor.id,
                    visitor_name=visitor.full_name or "Noma'lum",
                    visitor_username=visitor.username,
                )
                session.add(log)
                await session.commit()

                # Egasiga xabar
                v_name = visitor.full_name or "Noma'lum"
                v_username = f"@{visitor.username}" if visitor.username else "username yo'q"
                v_id = visitor.id

                if owner:
                    alert_text = (
                        f"🚨 <b>DIQQAT! Tuzoqqa tushdi!</b>\n\n"
                        f"👤 Kim kirdi: <b>{v_name}</b>\n"
                        f"📱 Username: {v_username}\n"
                        f"🆔 Telegram ID: <code>{v_id}</code>\n\n"
                        f"🕐 Vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                        f"💡 Bu odam sizning tuzoq havolangizni bosdi!"
                    )
                    try:
                        await message.bot.send_message(
                            chat_id=owner_id,
                            text=alert_text,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

                # Bosuvchiga — eganing shaxsiy xabari yoki standart
                decoy_text = (owner.decoy_message if owner and owner.decoy_message else DEFAULT_DECOY)
                await message.answer(decoy_text, parse_mode="HTML")
                return

    # ── Oddiy /start ────────────────────────────────────────────────────────
    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )

    now = datetime.now(timezone.utc)
    is_active = make_aware(user.subscription_end) and make_aware(user.subscription_end) > now

    status_text = (
        f"✅ Obuna faol — <b>{user.subscription_end.strftime('%d.%m.%Y')}</b> gacha"
        if is_active
        else "❌ Obuna yo'q"
    )

    welcome = (
        f"👋 Salom, <b>{message.from_user.full_name}</b>!\n\n"
        f"🕵️ <b>STALKER</b> — kim profilingizga kirayotganini bilib oling!\n\n"
        f"🪤 Tuzoq havolangizni bio yoki story'ga joylashtiring\n"
        f"🔔 Kimdir bossa — darhol xabar olasiz\n"
        f"👥 Kim bosganini ro'yxatdan ko'ring\n\n"
        f"📌 Holat: {status_text}\n\n"
        f"⬇️ Menyudan boshlang:"
    )
    await message.answer(welcome, parse_mode="HTML", reply_markup=main_menu_kb())


# ─── Balans / Obuna ko'rish ───────────────────────────────────────────────────

@router.callback_query(F.data == "show_balance")
async def show_balance(call: CallbackQuery, session: AsyncSession):
    user = await get_user(session, call.from_user.id)
    now = datetime.now(timezone.utc)
    sub_end = make_aware(user.subscription_end) if user else None

    if user and sub_end and sub_end > now:
        days_left = (sub_end - now).days
        end_date = user.subscription_end.strftime("%d.%m.%Y %H:%M")
        text = (
            f"💰 <b>Balansingiz:</b> {user.balance:,} so'm\n\n"
            f"✅ Obuna: <b>Faol</b>\n"
            f"📅 Tugash sanasi: <b>{end_date}</b>\n"
            f"⏳ Qolgan kunlar: <b>{days_left} kun</b>"
        )
    else:
        text = (
            f"💰 <b>Balansingiz:</b> {user.balance if user else 0:,} so'm\n\n"
            f"❌ Obuna: <b>Faol emas</b>\n\n"
            f"Botdan to'liq foydalanish uchun obuna sotib oling."
        )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    await call.answer()


# ─── Tuzoq havolasi ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "get_link")
async def get_link(call: CallbackQuery, session: AsyncSession):
    user = await get_user(session, call.from_user.id)
    if not user:
        await call.answer("Xatolik yuz berdi.", show_alert=True)
        return

    bot_info = await call.bot.get_me()
    bot_username = bot_info.username
    trap_link = f"https://t.me/{bot_username}?start=trap_{call.from_user.id}"

    # Umumiy bosishlar soni
    count = await get_trap_count(session, call.from_user.id)

    text = (
        f"🪤 <b>Sizning tuzoq havolangiz:</b>\n\n"
        f"<code>{trap_link}</code>\n\n"
        f"👆 Jami bosildi: <b>{count} marta</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Qanday ishlatiladi?</b>\n\n"
        f"1️⃣ Havolani nusxalab, telegram profilingizdagi "
        f"<b>Bio</b> bo'limiga yoki <b>Story</b>ga joylashtiring\n"
        f"2️⃣ Ustiga qiziqarli yozuv qo'ying:\n"
        f"   • <i>\"Men haqimda qiziqarli faktlar\"</i>\n"
        f"   • <i>\"Anonim fikr qoldiring\"</i>\n"
        f"   • <i>\"Shaxsiy blogim\"</i>\n\n"
        f"3️⃣ Kimdir bossa — <b>siz darhol xabar olasiz!</b> 🚨"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    await call.answer()


# ─── Kim bosdi — statistika ───────────────────────────────────────────────────

@router.callback_query(F.data == "trap_stats")
async def trap_stats(call: CallbackQuery, session: AsyncSession):
    logs = await get_trap_logs(session, call.from_user.id, limit=20)
    total = await get_trap_count(session, call.from_user.id)

    if not logs:
        text = (
            "👥 <b>Tuzoqqa tushganlar</b>\n\n"
            "Hali hech kim havolangizni bosmagan.\n\n"
            "🪤 Havolani profilingizga joylang!"
        )
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
        await call.answer()
        return

    lines = [f"👥 <b>Tuzoqqa tushganlar</b> (jami: {total} ta)\n"]
    for i, log in enumerate(logs, 1):
        uname = f"@{log.visitor_username}" if log.visitor_username else "—"
        date_str = make_aware(log.clicked_at).strftime("%d.%m %H:%M")
        lines.append(
            f"{i}. <b>{log.visitor_name}</b> | {uname}\n"
            f"    🆔 <code>{log.visitor_id}</code> | 🕐 {date_str}"
        )

    if total > 20:
        lines.append(f"\n<i>...va yana {total - 20} ta</i>")

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    await call.answer()


# ─── Tuzoq xabarini sozlash ───────────────────────────────────────────────────

@router.callback_query(F.data == "set_decoy")
async def set_decoy_menu(call: CallbackQuery, session: AsyncSession):
    user = await get_user(session, call.from_user.id)
    current = user.decoy_message if user and user.decoy_message else DEFAULT_DECOY

    text = (
        f"✏️ <b>Tuzoq xabarini sozlash</b>\n\n"
        f"Bu xabar havolangizni bosgan odamga ko'rsatiladi.\n\n"
        f"📄 <b>Hozirgi xabar:</b>\n"
        f"<blockquote>{current}</blockquote>\n\n"
        f"Quyidagi tugmalar orqali o'zgartiring:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=decoy_edit_kb())
    await call.answer()


@router.callback_query(F.data == "edit_decoy_text")
async def edit_decoy_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(DecoyState.waiting_message)
    await call.message.answer(
        "✏️ <b>Yangi tuzoq xabarini yozing:</b>\n\n"
        "HTML теглари ishlaydi:\n"
        "• <code>&lt;b&gt;qalin&lt;/b&gt;</code>\n"
        "• <code>&lt;i&gt;kursiv&lt;/i&gt;</code>\n"
        "• <code>&lt;code&gt;kod&lt;/code&gt;</code>\n\n"
        "<i>Misol: \"⏳ Yuklanmoqda... biroz kuting.\"</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await call.answer()


@router.callback_query(F.data == "reset_decoy")
async def reset_decoy(call: CallbackQuery, session: AsyncSession):
    user = await get_user(session, call.from_user.id)
    if user:
        user.decoy_message = None
        await session.commit()
    await call.message.edit_text(
        f"✅ <b>Xabar standartga qaytarildi!</b>\n\n"
        f"📄 Hozirgi xabar:\n<blockquote>{DEFAULT_DECOY}</blockquote>",
        parse_mode="HTML",
        reply_markup=decoy_edit_kb()
    )
    await call.answer()


@router.message(DecoyState.waiting_message)
async def save_decoy_message(message: Message, session: AsyncSession, state: FSMContext):
    new_text = message.text or message.caption
    if not new_text:
        await message.answer(
            "⚠️ Faqat <b>matn</b> yuboring.",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
        return

    if len(new_text) > 1000:
        await message.answer(
            "⚠️ Xabar juda uzun (maksimal 1000 belgi).",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
        return

    user = await get_user(session, message.from_user.id)
    if user:
        user.decoy_message = new_text
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ <b>Tuzoq xabari saqlandi!</b>\n\n"
        f"📄 Yangi xabar:\n<blockquote>{new_text}</blockquote>",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── Tariflar menyusi ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "pay_menu")
async def pay_menu(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    tariffs = await get_tariffs(session)
    if not tariffs:
        await call.message.edit_text(
            "⚠️ Hozircha faol tariflar yo'q.\nTez orada qo'shiladi!",
            reply_markup=main_menu_kb()
        )
        await call.answer()
        return
    text = (
        "💳 <b>Obuna tariflarini tanlang:</b>\n\n"
        "Sizga qulay bo'lgan paketni tanlang:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=tariffs_kb(tariffs))
    await call.answer()


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🏠 <b>Asosiy menyu</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    await call.answer()


# ─── Tarif tanlash ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tariff_"))
async def choose_tariff(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    tariff_id = int(call.data.split("_", 1)[1])
    tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff or not tariff.is_active:
        await call.answer("Tarif topilmadi yoki nofaol!", show_alert=True)
        return

    card = await get_active_card(session)
    card_number = card.card_number if card else "Karta mavjud emas"
    card_owner = card.card_owner if card else ""

    price_fmt = f"{tariff.price:,}".replace(",", " ")
    text = (
        f"📦 <b>{tariff.label} obuna</b>\n\n"
        f"💵 Narxi: <b>{price_fmt} so'm</b>\n"
        f"📅 Muddat: <b>{tariff.months} oy</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 To'lov kartasi:\n"
        f"<code>{card_number}</code>\n"
        f"👤 Egasi: <b>{card_owner}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Yuqoridagi kartaga <b>{price_fmt} so'm</b> o'tkazing,\n"
        f"so'ng chekni (screenshot) yuboring."
    )
    await state.update_data(tariff_id=tariff_id)
    await call.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=payment_confirm_kb(tariff_id)
    )
    await call.answer()


# ─── Chek yuborish ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("send_receipt_"))
async def ask_receipt(call: CallbackQuery, state: FSMContext):
    tariff_id = call.data.split("_", 2)[2]
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(PaymentState.waiting_receipt)
    await call.message.answer(
        "📸 <b>To'lov chekini yuboring</b>\n\n"
        "• Rasm (screenshot) <b>yoki</b>\n"
        "• Fayl sifatida ham yuborishingiz mumkin\n\n"
        "⬇️ Chekni yuboring:",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await call.answer()


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "❌ Bekor qilindi.",
        reply_markup=main_menu_kb()
    )
    await call.answer()


# Rasm — chek
@router.message(PaymentState.waiting_receipt, F.photo)
async def receive_receipt_photo(message: Message, session: AsyncSession, state: FSMContext):
    file_id = message.photo[-1].file_id
    await _process_receipt(message, session, state, file_id, is_photo=True)


# Fayl — chek
@router.message(PaymentState.waiting_receipt, F.document)
async def receive_receipt_document(message: Message, session: AsyncSession, state: FSMContext):
    file_id = message.document.file_id
    await _process_receipt(message, session, state, file_id, is_photo=False)


# Noto'g'ri narsa
@router.message(PaymentState.waiting_receipt)
async def receipt_wrong_type(message: Message):
    await message.answer(
        "⚠️ Iltimos, faqat <b>rasm yoki fayl</b> yuboring.\n\n"
        "To'lov cheki screenshot ko'rinishida bo'lishi kerak.",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


async def _process_receipt(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    file_id: str,
    is_photo: bool,
):
    data = await state.get_data()
    tariff_id = data.get("tariff_id")
    tariff = await get_tariff_by_id(session, int(tariff_id)) if tariff_id else None
    if not tariff:
        await message.answer("❌ Xatolik! Qaytadan boshlang /start")
        await state.clear()
        return

    payment = Payment(
        telegram_id=message.from_user.id,
        tariff_id=tariff.id,
        amount=tariff.price,
        months=tariff.months,
        receipt_file_id=file_id,
        status="pending",
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    price_fmt = f"{tariff.price:,}".replace(",", " ")
    await message.answer(
        f"✅ <b>Chek qabul qilindi!</b>\n\n"
        f"📦 Tarif: <b>{tariff.label}</b>\n"
        f"💵 Summa: <b>{price_fmt} so'm</b>\n\n"
        f"⏳ Admin tekshirib, obunani faollashtiradi.\n"
        f"Odatda 5–30 daqiqa ichida...",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

    from keyboards import payment_action_kb
    username_str = f"@{message.from_user.username}" if message.from_user.username else "username yo'q"
    admin_text = (
        f"💳 <b>Yangi to'lov!</b> #{payment.id}\n\n"
        f"👤 Foydalanuvchi: <b>{message.from_user.full_name}</b>\n"
        f"📱 {username_str}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📦 Tarif: <b>{tariff.label}</b>\n"
        f"💵 Summa: <b>{price_fmt} so'm</b>"
    )
    try:
        if is_photo:
            await message.bot.send_photo(
                chat_id=ADMIN_ID, photo=file_id,
                caption=admin_text, parse_mode="HTML",
                reply_markup=payment_action_kb(payment.id, message.from_user.id)
            )
        else:
            await message.bot.send_document(
                chat_id=ADMIN_ID, document=file_id,
                caption=admin_text, parse_mode="HTML",
                reply_markup=payment_action_kb(payment.id, message.from_user.id)
            )
    except Exception:
        try:
            await message.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text + f"\n\n⚠️ Chek fayli: <code>{file_id}</code>",
                parse_mode="HTML",
                reply_markup=payment_action_kb(payment.id, message.from_user.id)
            )
        except Exception:
            pass

    await state.clear()

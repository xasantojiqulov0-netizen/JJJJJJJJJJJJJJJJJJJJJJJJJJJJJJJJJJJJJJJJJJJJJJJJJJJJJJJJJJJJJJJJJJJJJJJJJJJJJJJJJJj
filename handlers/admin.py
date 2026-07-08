import io
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from config import ADMIN_ID
from database import (
    User, Payment, AdminCard, Tariff,
    get_stats, get_all_tariffs, get_tariff_by_id,
)
from keyboards import (
    admin_panel_kb, payment_action_kb,
    admin_tariffs_kb, admin_tariff_detail_kb,
)


def make_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


router = Router()


def is_admin(telegram_id: int) -> bool:
    return telegram_id == ADMIN_ID


# ─── FSM ──────────────────────────────────────────────────────────────────────

class AdminState(StatesGroup):
    add_card_number  = State()
    add_card_owner   = State()
    broadcast_media  = State()
    manual_sub       = State()
    block_user       = State()
    # Tariff CRUD
    tariff_add_label  = State()
    tariff_add_months = State()
    tariff_add_price  = State()
    tariff_edit_label  = State()
    tariff_edit_months = State()
    tariff_edit_price  = State()


# ─── /admin ───────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 <b>Admin panel</b>", parse_mode="HTML", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "adm_back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    await state.clear()
    await call.message.edit_text("🛠 <b>Admin panel</b>", parse_mode="HTML", reply_markup=admin_panel_kb())
    await call.answer()


# ─── Statistika ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    stats = await get_stats(session)
    text = (
        f"📊 <b>Bot statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"✅ Faol obunalar: <b>{stats['subscribed']}</b>\n"
        f"📅 Bugun tasdiqlangan to'lovlar: <b>{stats['today_payments']}</b>\n"
        f"💰 Jami daromad: <b>{stats['total_income']:,} so'm</b>"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_panel_kb())
    await call.answer()


# ─── Tariflar ro'yxati ────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_tariffs")
async def adm_tariffs(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    tariffs = await get_all_tariffs(session)
    text = (
        f"📦 <b>Tariflar boshqaruvi</b>\n\n"
        f"Jami: <b>{len(tariffs)} ta</b>\n"
        f"✅ — faol  |  ❌ — nofaol\n\n"
        f"Tahrirlash uchun tarifni bosing:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_tariffs_kb(tariffs))
    await call.answer()


# ─── Tarif detali ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_tariff_"))
async def adm_tariff_detail(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    # "adm_tariff_add" ni bu handler ushlamamasligi uchun
    raw = call.data.split("_")  # ['adm', 'tariff', '<id>']
    if len(raw) < 3 or not raw[2].isdigit():
        return  # adm_tariff_add va boshqalar boshqa handler'da
    tariff_id = int(raw[2])
    tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        await call.answer("Tarif topilmadi!", show_alert=True)
        return
    status = "✅ Faol" if tariff.is_active else "❌ Nofaol"
    price_fmt = f"{tariff.price:,}".replace(",", " ")
    text = (
        f"📦 <b>Tarif #{tariff.id}</b>\n\n"
        f"🏷 Nom: <b>{tariff.label}</b>\n"
        f"📅 Muddat: <b>{tariff.months} oy</b>\n"
        f"💵 Narx: <b>{price_fmt} so'm</b>\n"
        f"📌 Holat: {status}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_tariff_detail_kb(tariff))
    await call.answer()


# ─── Yangi tarif qo'shish ─────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_tariff_add")
async def adm_tariff_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    await state.set_state(AdminState.tariff_add_label)
    await call.message.answer(
        "➕ <b>Yangi tarif qo'shish</b>\n\n"
        "1/3 — Tarif nomini kiriting:\n"
        "<i>Misol: 2 oylik</i>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.tariff_add_label)
async def adm_tariff_add_label(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(label=message.text.strip())
    await state.set_state(AdminState.tariff_add_months)
    await message.answer(
        "2/3 — Necha oy?\n<i>Misol: 2</i>",
        parse_mode="HTML"
    )


@router.message(AdminState.tariff_add_months)
async def adm_tariff_add_months(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit() or int(message.text.strip()) < 1:
        await message.answer("❌ Faqat musbat son kiriting. Masalan: <code>2</code>", parse_mode="HTML")
        return
    await state.update_data(months=int(message.text.strip()))
    await state.set_state(AdminState.tariff_add_price)
    await message.answer(
        "3/3 — Narxini so'mda kiriting:\n<i>Misol: 50000</i>",
        parse_mode="HTML"
    )


@router.message(AdminState.tariff_add_price)
async def adm_tariff_add_price(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    price_str = message.text.strip().replace(" ", "").replace(",", "")
    if not price_str.isdigit() or int(price_str) < 1:
        await message.answer("❌ Faqat musbat son kiriting. Masalan: <code>50000</code>", parse_mode="HTML")
        return
    data = await state.get_data()
    result = await session.execute(select(func.count(Tariff.id)))
    count = result.scalar() or 0
    tariff = Tariff(
        label=data["label"],
        months=data["months"],
        price=int(price_str),
        is_active=True,
        sort_order=count,
    )
    session.add(tariff)
    await session.commit()
    await state.clear()
    price_fmt = f"{tariff.price:,}".replace(",", " ")
    await message.answer(
        f"✅ <b>Tarif qo'shildi!</b>\n\n"
        f"🏷 Nom: <b>{tariff.label}</b>\n"
        f"📅 Muddat: <b>{tariff.months} oy</b>\n"
        f"💵 Narx: <b>{price_fmt} so'm</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ─── Tarif tahrirlash — Nom ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_t_label_"))
async def adm_t_label_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    tariff_id = int(call.data.split("_")[3])
    await state.update_data(edit_tariff_id=tariff_id)
    await state.set_state(AdminState.tariff_edit_label)
    await call.message.answer(
        "✏️ Yangi nom kiriting:\n<i>Misol: 2 oylik</i>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.tariff_edit_label)
async def adm_t_label_save(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    tariff = await get_tariff_by_id(session, data["edit_tariff_id"])
    if tariff:
        tariff.label = message.text.strip()
        await session.commit()
    await state.clear()
    await message.answer(
        f"✅ Nom o'zgartirildi: <b>{tariff.label}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ─── Tarif tahrirlash — Narx ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_t_price_"))
async def adm_t_price_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    tariff_id = int(call.data.split("_")[3])
    await state.update_data(edit_tariff_id=tariff_id)
    await state.set_state(AdminState.tariff_edit_price)
    await call.message.answer(
        "💵 Yangi narxni so'mda kiriting:\n<i>Misol: 60000</i>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.tariff_edit_price)
async def adm_t_price_save(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    price_str = message.text.strip().replace(" ", "").replace(",", "")
    if not price_str.isdigit() or int(price_str) < 1:
        await message.answer("❌ Faqat musbat son kiriting.", parse_mode="HTML")
        return
    data = await state.get_data()
    tariff = await get_tariff_by_id(session, data["edit_tariff_id"])
    if tariff:
        tariff.price = int(price_str)
        await session.commit()
    await state.clear()
    price_fmt = f"{tariff.price:,}".replace(",", " ")
    await message.answer(
        f"✅ Narx o'zgartirildi: <b>{price_fmt} so'm</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ─── Tarif tahrirlash — Oylar ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_t_months_"))
async def adm_t_months_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    tariff_id = int(call.data.split("_")[3])
    await state.update_data(edit_tariff_id=tariff_id)
    await state.set_state(AdminState.tariff_edit_months)
    await call.message.answer(
        "📅 Yangi oy sonini kiriting:\n<i>Misol: 2</i>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.tariff_edit_months)
async def adm_t_months_save(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit() or int(message.text.strip()) < 1:
        await message.answer("❌ Faqat musbat son kiriting.", parse_mode="HTML")
        return
    data = await state.get_data()
    tariff = await get_tariff_by_id(session, data["edit_tariff_id"])
    if tariff:
        tariff.months = int(message.text.strip())
        await session.commit()
    await state.clear()
    await message.answer(
        f"✅ Muddat o'zgartirildi: <b>{tariff.months} oy</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ─── Tarif yoqish / o'chirish (toggle) ───────────────────────────────────────

@router.callback_query(F.data.startswith("adm_t_toggle_"))
async def adm_t_toggle(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    tariff_id = int(call.data.split("_")[3])
    tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        return await call.answer("Tarif topilmadi!", show_alert=True)
    tariff.is_active = not tariff.is_active
    await session.commit()
    status = "✅ Yoqildi" if tariff.is_active else "❌ O'chirildi"
    await call.answer(f"{status}: {tariff.label}", show_alert=True)
    # Yangilangan detalni ko'rsatamiz
    price_fmt = f"{tariff.price:,}".replace(",", " ")
    status_str = "✅ Faol" if tariff.is_active else "❌ Nofaol"
    text = (
        f"📦 <b>Tarif #{tariff.id}</b>\n\n"
        f"🏷 Nom: <b>{tariff.label}</b>\n"
        f"📅 Muddat: <b>{tariff.months} oy</b>\n"
        f"💵 Narx: <b>{price_fmt} so'm</b>\n"
        f"📌 Holat: {status_str}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_tariff_detail_kb(tariff))


# ─── Tarifni butunlay o'chirish ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_t_delete_"))
async def adm_t_delete(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    tariff_id = int(call.data.split("_")[3])
    tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        return await call.answer("Tarif topilmadi!", show_alert=True)
    label = tariff.label
    await session.delete(tariff)
    await session.commit()
    tariffs = await get_all_tariffs(session)
    await call.message.edit_text(
        f"🗑 <b>{label}</b> tarifi o'chirildi.\n\n📦 Tariflar ro'yxati:",
        parse_mode="HTML",
        reply_markup=admin_tariffs_kb(tariffs)
    )
    await call.answer()


# ─── Karta qo'shish ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_add_card")
async def adm_add_card(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    await state.set_state(AdminState.add_card_number)
    await call.message.answer(
        "💳 Yangi karta raqamini kiriting:\n\n"
        "Misol: <code>8600 1234 5678 9012</code>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.add_card_number)
async def adm_card_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(card_number=message.text.strip())
    await state.set_state(AdminState.add_card_owner)
    await message.answer("👤 Karta egasining ismini kiriting:")


@router.message(AdminState.add_card_owner)
async def adm_card_owner(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    await session.execute(update(AdminCard).values(is_active=False))
    card = AdminCard(card_number=data["card_number"], card_owner=message.text.strip())
    session.add(card)
    await session.commit()
    await state.clear()
    await message.answer(
        f"✅ Karta muvaffaqiyatli qo'shildi!\n\n"
        f"💳 {data['card_number']}\n"
        f"👤 {message.text.strip()}",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ─── Kutayotgan to'lovlar ─────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_pending")
async def adm_pending(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    result = await session.execute(
        select(Payment).where(Payment.status == "pending").order_by(Payment.created_at)
    )
    payments = result.scalars().all()
    if not payments:
        await call.message.edit_text("✅ Kutayotgan to'lovlar yo'q.", reply_markup=admin_panel_kb())
        return await call.answer()

    await call.message.edit_text(
        f"⏳ <b>Kutayotgan to'lovlar: {len(payments)} ta</b>",
        parse_mode="HTML", reply_markup=admin_panel_kb()
    )
    from database import get_tariff_by_id
    for pay in payments[:10]:
        tariff = await get_tariff_by_id(session, pay.tariff_id)
        tariff_name = tariff.label if tariff else f"#{pay.tariff_id}"
        text = (
            f"💳 To'lov #{pay.id}\n"
            f"👤 ID: <code>{pay.telegram_id}</code>\n"
            f"📦 Tarif: {tariff_name}\n"
            f"💵 {pay.amount:,} so'm\n"
            f"📅 {pay.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        try:
            if pay.receipt_file_id:
                await call.bot.send_photo(
                    chat_id=call.from_user.id, photo=pay.receipt_file_id,
                    caption=text, parse_mode="HTML",
                    reply_markup=payment_action_kb(pay.id, pay.telegram_id)
                )
            else:
                await call.bot.send_message(
                    chat_id=call.from_user.id, text=text, parse_mode="HTML",
                    reply_markup=payment_action_kb(pay.id, pay.telegram_id)
                )
        except Exception:
            await call.bot.send_message(
                chat_id=call.from_user.id, text=text, parse_mode="HTML",
                reply_markup=payment_action_kb(pay.id, pay.telegram_id)
            )
    await call.answer()


# ─── To'lovni tasdiqlash ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    parts = call.data.split("_")
    pay_id, tg_id = int(parts[1]), int(parts[2])
    result = await session.execute(select(Payment).where(Payment.id == pay_id))
    payment = result.scalar_one_or_none()
    if not payment or payment.status != "pending":
        return await call.answer("Bu to'lov allaqachon qayta ishlangan!", show_alert=True)
    payment.status = "approved"
    result2 = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result2.scalar_one_or_none()
    if user:
        now = datetime.now(timezone.utc)
        base = make_aware(user.subscription_end)
        base = base if (base and base > now) else now
        user.subscription_end = base + timedelta(days=payment.months * 30)
        user.is_subscribed = True
        user.balance += payment.amount
    await session.commit()
    from database import get_tariff_by_id
    tariff = await get_tariff_by_id(session, payment.tariff_id)
    tariff_name = tariff.label if tariff else f"#{payment.tariff_id}"
    end_date = user.subscription_end.strftime("%d.%m.%Y") if user and user.subscription_end else "—"
    try:
        await call.bot.send_message(
            chat_id=tg_id,
            text=(
                f"🎉 <b>Obuna faollashtirildi!</b>\n\n"
                f"📦 Tarif: <b>{tariff_name}</b>\n"
                f"📅 Tugash sanasi: <b>{end_date}</b>\n\n"
                f"Botdan to'liq foydalaning! 🚀"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass
    try:
        if call.message.caption is not None:
            await call.message.edit_caption(
                caption=call.message.caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML"
            )
        else:
            await call.message.edit_text(
                call.message.text + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML"
            )
    except Exception:
        pass
    await call.answer("✅ Obuna faollashtirildi!")


# ─── To'lovni rad etish ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    parts = call.data.split("_")
    pay_id, tg_id = int(parts[1]), int(parts[2])
    result = await session.execute(select(Payment).where(Payment.id == pay_id))
    payment = result.scalar_one_or_none()
    if not payment or payment.status != "pending":
        return await call.answer("Bu to'lov allaqachon qayta ishlangan!", show_alert=True)
    payment.status = "rejected"
    await session.commit()
    try:
        await call.bot.send_message(
            chat_id=tg_id,
            text=(
                "❌ <b>To'lovingiz rad etildi.</b>\n\n"
                "Muammo bo'lsa, admin bilan bog'laning.\n"
                "Qayta urinib ko'ring: /start"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass
    try:
        if call.message.caption is not None:
            await call.message.edit_caption(
                caption=(call.message.caption or "") + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML"
            )
        else:
            await call.message.edit_text(
                (call.message.text or "") + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML"
            )
    except Exception:
        pass
    await call.answer("❌ To'lov rad etildi.")


# ─── Reklama yuborish ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    await state.set_state(AdminState.broadcast_media)
    await call.message.answer(
        "📢 <b>Reklama xabarini yuboring</b>\n\n"
        "Matn, rasm yoki video yuborishingiz mumkin.\n"
        "Barcha foydalanuvchilarga yuboriladi.",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.broadcast_media)
async def adm_broadcast_send(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    result = await session.execute(
        select(User.telegram_id).where(User.is_blocked == False)
    )
    user_ids = [row[0] for row in result.fetchall()]
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            if message.photo:
                await message.bot.send_photo(uid, message.photo[-1].file_id,
                    caption=message.caption or "", parse_mode="HTML")
            elif message.video:
                await message.bot.send_video(uid, message.video.file_id,
                    caption=message.caption or "", parse_mode="HTML")
            else:
                await message.bot.send_message(uid, message.text or "", parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📢 Reklama yuborildi!\n✅ Muvaffaqiyatli: {sent}\n❌ Xato: {failed}",
        reply_markup=admin_panel_kb()
    )


# ─── Excel ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_excel")
async def adm_excel(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    result = await session.execute(select(User).order_by(User.joined_at.desc()))
    users = result.scalars().all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Foydalanuvchilar"
    headers = ["#", "Telegram ID", "Ism", "Username", "Obuna", "Tugash", "Balans", "Blok", "Ro'yxat sanasi"]
    hfill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    hfont = Font(color="FFFFFF", bold=True)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hfill; cell.font = hfont
        cell.alignment = Alignment(horizontal="center")
    for w, col in zip([5,16,25,20,12,18,14,10,22], range(1, 10)):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w
    now = datetime.now(timezone.utc)
    for i, u in enumerate(users, 1):
        sub_end = make_aware(u.subscription_end)
        ws.append([
            i, u.telegram_id, u.full_name,
            f"@{u.username}" if u.username else "—",
            "Faol" if (sub_end and sub_end > now) else "Faol emas",
            u.subscription_end.strftime("%d.%m.%Y") if u.subscription_end else "—",
            u.balance,
            "Ha" if u.is_blocked else "Yo'q",
            u.joined_at.strftime("%d.%m.%Y %H:%M") if u.joined_at else "—",
        ])
    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    fname = f"users_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    await call.message.answer_document(
        BufferedInputFile(buf.read(), filename=fname),
        caption=f"📥 Foydalanuvchilar ro'yxati ({len(users)} ta)"
    )
    await call.answer()


# ─── Obuna qo'lda berish ──────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_subs")
async def adm_subs(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    await state.set_state(AdminState.manual_sub)
    await call.message.answer(
        "📋 <b>Qo'lda obuna berish</b>\n\n"
        "Foydalanuvchi ID va oylar sonini yuboring:\n"
        "<code>1234567890 3</code>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.manual_sub)
async def adm_manual_sub(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await message.answer("❌ Noto'g'ri format. Misol: <code>1234567890 3</code>", parse_mode="HTML")
        return
    tg_id, months = int(parts[0]), int(parts[1])
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer(f"❌ ID {tg_id} foydalanuvchi topilmadi!")
        return
    now = datetime.now(timezone.utc)
    base = make_aware(user.subscription_end)
    base = base if (base and base > now) else now
    user.subscription_end = base + timedelta(days=months * 30)
    user.is_subscribed = True
    await session.commit()
    await state.clear()
    end_date = user.subscription_end.strftime("%d.%m.%Y")
    await message.answer(
        f"✅ <b>{user.full_name}</b> ga {months} oylik obuna berildi.\n"
        f"📅 Tugash: <b>{end_date}</b>",
        parse_mode="HTML", reply_markup=admin_panel_kb()
    )
    try:
        await message.bot.send_message(
            tg_id,
            f"🎉 Sizga <b>{months} oylik</b> obuna berildi!\n📅 Tugash sanasi: <b>{end_date}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─── Blok / Blokdan chiqarish ─────────────────────────────────────────────────

@router.callback_query(F.data == "adm_block")
async def adm_block_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)
    await state.set_state(AdminState.block_user)
    await call.message.answer(
        "🚫 <b>Foydalanuvchini bloklash / blokdan chiqarish</b>\n\n"
        "Foydalanuvchi Telegram ID sini kiriting:\n<code>1234567890</code>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.block_user)
async def adm_toggle_block(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam kiriting.")
        return
    tg_id = int(message.text.strip())
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer(f"❌ ID {tg_id} foydalanuvchi topilmadi!")
        await state.clear()
        return
    user.is_blocked = not user.is_blocked
    await session.commit()
    await state.clear()
    status = "🚫 Bloklandi" if user.is_blocked else "✅ Blokdan chiqarildi"
    await message.answer(
        f"{status}\n\n👤 <b>{user.full_name}</b>\n🆔 <code>{tg_id}</code>",
        parse_mode="HTML", reply_markup=admin_panel_kb()
    )
    try:
        msg = ("🚫 Hisobingiz bloklandi.\nAdmin bilan bog'laning."
               if user.is_blocked else
               "✅ Blok olib tashlandi. Botdan foydalaning: /start")
        await message.bot.send_message(tg_id, msg)
    except Exception:
        pass

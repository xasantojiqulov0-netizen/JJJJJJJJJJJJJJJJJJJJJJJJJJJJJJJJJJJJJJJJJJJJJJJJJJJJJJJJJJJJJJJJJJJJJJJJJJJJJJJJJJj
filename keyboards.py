from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Tariff


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Obuna sotib olish",       callback_data="pay_menu")],
        [InlineKeyboardButton(text="💰 Mening obunam",           callback_data="show_balance")],
        [InlineKeyboardButton(text="🪤 Tuzoq havolam",           callback_data="get_link")],
        [InlineKeyboardButton(text="👥 Kim bosdi?",              callback_data="trap_stats")],
        [InlineKeyboardButton(text="✏️ Tuzoq xabarini sozlash",  callback_data="set_decoy")],
    ])


def tariffs_kb(tariffs: list[Tariff]) -> InlineKeyboardMarkup:
    rows = []
    for t in tariffs:
        price_fmt = f"{t.price:,}".replace(",", " ")
        rows.append([
            InlineKeyboardButton(
                text=f"📦 {t.label} — {price_fmt} so'm",
                callback_data=f"tariff_{t.id}"
            )
        ])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_confirm_kb(tariff_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To'lov chekini yuborish", callback_data=f"send_receipt_{tariff_id}")],
        [InlineKeyboardButton(text="🔙 Tariflar", callback_data="pay_menu")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
    ])


def decoy_edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Xabarni o'zgartirish", callback_data="edit_decoy_text")],
        [InlineKeyboardButton(text="🗑 Standartga qaytarish",  callback_data="reset_decoy")],
        [InlineKeyboardButton(text="🔙 Orqaga",                callback_data="back_main")],
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika",            callback_data="adm_stats")],
        [InlineKeyboardButton(text="💳 Karta qo'shish",        callback_data="adm_add_card")],
        [InlineKeyboardButton(text="📦 Tariflar",              callback_data="adm_tariffs")],
        [InlineKeyboardButton(text="⏳ Kutayotgan to'lovlar",  callback_data="adm_pending")],
        [InlineKeyboardButton(text="📋 Obuna berish",          callback_data="adm_subs")],
        [InlineKeyboardButton(text="🚫 Foydalanuvchi blok",    callback_data="adm_block")],
        [InlineKeyboardButton(text="📢 Reklama yuborish",      callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📥 Excel yuklab olish",    callback_data="adm_excel")],
    ])


def admin_tariffs_kb(tariffs: list[Tariff]) -> InlineKeyboardMarkup:
    """Admin uchun barcha tariflar ro'yxati."""
    rows = []
    for t in tariffs:
        status = "✅" if t.is_active else "❌"
        price_fmt = f"{t.price:,}".replace(",", " ")
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {t.label} | {t.months} oy | {price_fmt} so'm",
                callback_data=f"adm_tariff_{t.id}"
            )
        ])
    rows.append([InlineKeyboardButton(text="➕ Yangi tarif qo'shish", callback_data="adm_tariff_add")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_tariff_detail_kb(tariff: Tariff) -> InlineKeyboardMarkup:
    """Bitta tarif boshqaruv tugmalari."""
    toggle_text = "❌ O'chirish" if tariff.is_active else "✅ Yoqish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Nomini o'zgartirish",  callback_data=f"adm_t_label_{tariff.id}")],
        [InlineKeyboardButton(text="💵 Narxini o'zgartirish", callback_data=f"adm_t_price_{tariff.id}")],
        [InlineKeyboardButton(text="📅 Oyini o'zgartirish",   callback_data=f"adm_t_months_{tariff.id}")],
        [InlineKeyboardButton(text=toggle_text,               callback_data=f"adm_t_toggle_{tariff.id}")],
        [InlineKeyboardButton(text="🗑 O'chirish",            callback_data=f"adm_t_delete_{tariff.id}")],
        [InlineKeyboardButton(text="🔙 Tariflar ro'yxati",   callback_data="adm_tariffs")],
    ])


def payment_action_kb(payment_id: int, telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{payment_id}_{telegram_id}"),
            InlineKeyboardButton(text="❌ Rad etish",  callback_data=f"reject_{payment_id}_{telegram_id}"),
        ]
    ])

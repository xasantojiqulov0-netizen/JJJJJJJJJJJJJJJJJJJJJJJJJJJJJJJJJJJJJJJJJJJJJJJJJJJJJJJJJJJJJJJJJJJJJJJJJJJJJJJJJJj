"""
APScheduler orqali ishlaydi:
- Har kunda bir marta obunasi tugagan yoki 1-3 kun qolgan foydalanuvchilarga
  avtomatik eslatma xabari yuboradi.
- Obunasi tugaganlarni is_subscribed=False qilib belgilaydi.
"""
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update

from database import SessionLocal, User


REMINDER_DAYS = [3, 1]  # Necha kun qolganda eslatma yuborilsin


async def check_subscriptions(bot: Bot):
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)

        def aware(dt):
            if dt is None:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        # 1) Obunasi tugaganlarni o'chirish
        expired_result = await session.execute(
            select(User).where(User.is_subscribed == True)
        )
        expired_users = expired_result.scalars().all()

        for user in expired_users:
            if aware(user.subscription_end) and aware(user.subscription_end) <= now:
                user.is_subscribed = False
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="pay_menu")]
                ])
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            "🔴 <b>Obunangiz tugadi!</b>\n\n"
                            "Botdan foydalanishni davom ettirish uchun obunani yangilang.\n\n"
                            "⬇️ Hoziroq to'ldiring:"
                        ),
                        parse_mode="HTML",
                        reply_markup=kb
                    )
                except Exception:
                    pass

        await session.commit()

        # 2) Obunasi tugashiga 1-3 kun qolganlarni eslatish
        for days in REMINDER_DAYS:
            remind_result = await session.execute(
                select(User).where(User.is_subscribed == True)
            )
            remind_users = remind_result.scalars().all()

            for user in remind_users:
                sub_end = aware(user.subscription_end)
                if not sub_end:
                    continue
                diff = (sub_end - now).total_seconds() / 3600  # soatlarda
                # days kun qolgan bo'lsa (±1 soat aniqlik)
                if not (days * 24 - 1 <= diff <= days * 24 + 1):
                    continue
                end_date = sub_end.strftime("%d.%m.%Y")
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Obunani yangilash", callback_data="pay_menu")]
                ])
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"⚠️ <b>Diqqat!</b>\n\n"
                            f"Obunangiz <b>{days} kun</b> ichida tugaydi.\n"
                            f"📅 Tugash sanasi: <b>{end_date}</b>\n\n"
                            f"Uzluksiz foydalanish uchun obunani uzaytiring:"
                        ),
                        parse_mode="HTML",
                        reply_markup=kb
                    )
                except Exception:
                    pass


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    # Har kuni 09:00 da ishlaydi
    scheduler.add_job(
        check_subscriptions,
        trigger="cron",
        hour=9,
        minute=0,
        args=[bot],
        id="subscription_checker",
        replace_existing=True,
    )
    return scheduler

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from middlewares import DbSessionMiddleware, SubscriptionMiddleware
from handlers import user, admin
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # DB jadvallarini yaratish
    await init_db()
    logger.info("Database initialized ✅")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Middleware'larni ulash (tartib muhim)
    dp.update.middleware(DbSessionMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Handler'larni ro'yxatdan o'tkazish
    dp.include_router(admin.router)   # Admin avval (prioritet yuqori)
    dp.include_router(user.router)

    # Scheduler'ni ishga tushirish
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started ✅")

    logger.info("Bot starting... 🤖")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from loguru import logger
from config import BOT_TOKEN
from database import init_db
from bot.handlers import router
from utils.scheduler import background_worker

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="set_filter", description="Установить фильтр (JSON)"),
        BotCommand(command="view_filter", description="Просмотреть текущий фильтр"),
        BotCommand(command="status", description="Статус системы"),
    ]
    await bot.set_my_commands(commands)

async def main():
    await init_db()
    logger.info("Database initialized")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await set_commands(bot)
    asyncio.create_task(background_worker(bot))
    logger.info("Bot started polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
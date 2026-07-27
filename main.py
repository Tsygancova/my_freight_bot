import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from loguru import logger
import os
from aiohttp import web

from config import BOT_TOKEN
from database import init_db
from bot.handlers import router
from utils.scheduler import background_worker

from bot.middlewares import LoggingMiddleware
# внутри main после создания dp
dp.update.middleware(LoggingMiddleware())

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    await site.start()
    logger.info(f"Web server started on port {os.environ.get('PORT', 8080)}")

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="set_filter", description="Настроить фильтры"),
        BotCommand(command="view_filter", description="Показать фильтры"),
        BotCommand(command="reset_filter", description="Сбросить фильтры"),
        BotCommand(command="history", description="История заказов (дни)"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="favorites", description="Избранное"),
        BotCommand(command="favorite", description="Добавить в избранное по ID"),
        BotCommand(command="unfavorite", description="Удалить из избранного"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="tutorial", description="Обучение"),
        BotCommand(command="status", description="Статус"),
    ]
    await bot.set_my_commands(commands)

bot = Bot(token=BOT_TOKEN)
# Сброс вебхука (важно для работы polling)
await bot.delete_webhook(drop_pending_updates=True)

async def main():
    await init_db()
    logger.info("Database initialized")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await set_commands(bot)

    # Запускаем веб-сервер, чтобы Render не ругался на отсутствие портов
    await start_web_server()

    # Запускаем фоновый сбор заказов
    asyncio.create_task(background_worker(bot))
    logger.info("Bot started polling...")

    # Запускаем поллинг (этот вызов теперь внутри async def main())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
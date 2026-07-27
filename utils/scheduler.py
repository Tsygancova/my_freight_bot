import asyncio
from loguru import logger
from config import PLATFORMS, POLL_INTERVAL
from adapters import get_adapter
from filters import match_filter
from database import async_session, save_order
from sqlalchemy import select
from database import UserFilter

async def fetch_orders_for_user(user_id: int, user_filter: dict, bot):
    for platform_cfg in PLATFORMS:
        if not platform_cfg.get("enabled", True):
            continue
        adapter = get_adapter(platform_cfg)
        try:
            orders = await adapter.fetch_orders()
            for order in orders:
                await save_order(user_id, order)
                if match_filter(order, user_filter):
                    text = (f"🔔 Новый заказ!\n"
                            f"📦 {order['origin_city']} → {order['dest_city']}\n"
                            f"⚖️ Вес: {order['weight_kg']} кг\n"
                            f"📐 Объём: {order['volume_m3']} м³\n"
                            f"💰 {order['price_eur']} €\n"
                            f"🏷️ Платформа: {order['platform']}")
                    await bot.send_message(user_id, text)
        except Exception as e:
            logger.error(f"Error fetching from {platform_cfg['name']}: {e}")

async def background_worker(bot):
    while True:
        try:
            async with async_session() as session:
                result = await session.execute(select(UserFilter))
                all_filters = result.scalars().all()
            
            tasks = []
            for uf in all_filters:
                user_id = uf.user_id
                filter_data = uf.filter_data or {}
                tasks.append(fetch_orders_for_user(user_id, filter_data, bot))
            
            if tasks:
                await asyncio.gather(*tasks)
            
            await asyncio.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Background worker error: {e}")
            await asyncio.sleep(POLL_INTERVAL)
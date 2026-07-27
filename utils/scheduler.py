import asyncio
from loguru import logger
from config import PLATFORMS, POLL_INTERVAL
from adapters import get_adapter
from filters import match_filter
from database import async_session, save_order, add_favorite
from sqlalchemy import select
from database import UserFilter, Order
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
                    # Кнопки
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🗺️ Карта",
                                url=f"https://www.google.com/maps/dir/{order['origin_city']}+{order['origin_country']}/{order['dest_city']}+{order['dest_country']}"
                            ),
                            InlineKeyboardButton(
                                text="⭐ В избранное",
                                callback_data=f"fav_add_{order['platform']}_{order['id']}"
                            )
                        ]
                    ])
                    
                    # Объёмный вес (если есть объём)
                    volume_weight = None
                    if order.get('volume_m3') and order.get('weight_kg'):
                        volume_weight = round(order['volume_m3'] * 250, 1)
                        chargeable = max(order['weight_kg'], volume_weight)
                    else:
                        chargeable = order.get('weight_kg', 'н/д')
                    
                    # Проверка ADR (если есть un_number)
                    adr_text = ""
                    if order.get('un_number'):
                        adr_text = f"\n⚠️ UN {order['un_number']} – возможно опасный груз!"
                    
                    # Паллеты
                    pallets_text = f"{order.get('pallets', 'н/д')} палл."
                    
                    text = (f"🔔 Новый заказ!\n"
                        f"📦 {order['origin_city']} → {order['dest_city']}\n"
                        f"⚖️ Вес: {order['weight_kg']} кг"
                        f"{f' (объёмный: {volume_weight} кг, оплачиваемый: {chargeable} кг)' if volume_weight else ''}\n"
                        f"📦 Паллет: {pallets_text}\n"
                        f"💰 {order['price_eur']} €\n"
                        f"🆔 ID: {order['id']}\n"   # <-- ЭТА СТРОЧКА
                        f"🏷️ Платформа: {order['platform']}"
                        f"{adr_text}")
                    await bot.send_message(user_id, text, reply_markup=keyboard)
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
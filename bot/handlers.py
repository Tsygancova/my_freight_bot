from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select, func
from datetime import datetime
import re

from database import (
    async_session, User, UserFilter, Order, Favorite, AcceptedOrder,
    get_orders_for_user, add_favorite, remove_favorite, get_favorites, accept_order
)
from filters import match_filter

router = Router()

# ---- Состояния для фильтров ----
class FilterForm(StatesGroup):
    origin_countries = State()
    dest_countries = State()
    max_weight = State()
    max_pallets = State()
    min_price = State()

# ---- Клавиатура для пропуска ----
skip_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏩ Пропустить")],
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# ---- Главное меню ----
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="🔧 Настроить фильтры", callback_data="menu_set_filter")],
        [InlineKeyboardButton(text="📋 Показать фильтры", callback_data="menu_view_filter")],
        [InlineKeyboardButton(text="🔄 Сбросить фильтры", callback_data="menu_reset_filter")],
        [InlineKeyboardButton(text="📜 История заказов", callback_data="menu_history")],
        [InlineKeyboardButton(text="⭐ Избранное", callback_data="menu_favorites")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="menu_stats")],
        [InlineKeyboardButton(text="📖 Помощь", callback_data="menu_help")],
        [InlineKeyboardButton(text="📚 Обучение", callback_data="menu_tutorial")],
        [InlineKeyboardButton(text="📡 Статус", callback_data="menu_status")],
        [InlineKeyboardButton(text="⏸️ Пауза", callback_data="menu_pause")],
        [InlineKeyboardButton(text="▶️ Возобновить", callback_data="menu_resume")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---- /start ----
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            session.add(User(id=user_id))
            await session.commit()
    await message.answer(
        "🚚 Привет! Я бот для поиска заказов на Fiat Doblò.\n"
        "Используй меню ниже или команды.\n"
        "Напиши /help для списка команд или /tutorial для обучения.",
        reply_markup=get_main_menu()
    )

# ---- Обработчики меню ----
@router.callback_query(lambda c: c.data.startswith("menu_"))
async def process_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.replace("menu_", "")
    await callback.answer()
    
    if action == "set_filter":
        await cmd_set_filter(callback.message, state)
    elif action == "view_filter":
        await cmd_view_filter(callback.message)
    elif action == "reset_filter":
        await cmd_reset_filter(callback.message)
    elif action == "history":
        await cmd_history(callback.message)
    elif action == "favorites":
        await cmd_favorites(callback.message)
    elif action == "stats":
        await cmd_stats(callback.message)
    elif action == "help":
        await cmd_help(callback.message)
    elif action == "tutorial":
        await cmd_tutorial(callback.message)
    elif action == "status":
        await cmd_status(callback.message)
    elif action == "pause":
        await cmd_pause(callback.message)
    elif action == "resume":
        await cmd_resume(callback.message)

# ---- /set_filter (пошагово) ----
@router.message(Command("set_filter"))
async def cmd_set_filter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Начинаем настройку фильтров.\n\n"
        "Введите **страны отправления** (коды через запятую, например: NL, BE, DE).\n"
        "Или нажмите «Пропустить».",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    await state.set_state(FilterForm.origin_countries)

@router.message(FilterForm.origin_countries)
async def process_origin_countries(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏩ Пропустить":
        await state.update_data(origin_countries=[])
        await message.answer("✅ Пропущено.", reply_markup=ReplyKeyboardRemove())
        await ask_dest_countries(message, state)
        return
    elif text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Настройка отменена.", reply_markup=ReplyKeyboardRemove())
        return
    
    if text:
        countries = [c.strip().upper() for c in text.split(',') if c.strip()]
        valid = [c for c in countries if re.match(r'^[A-Z]{2}$', c)]
        if not valid:
            await message.answer("❌ Неверный формат. Используйте двухбуквенные коды через запятую (например, NL, BE).")
            return
        await state.update_data(origin_countries=valid)
    else:
        await state.update_data(origin_countries=[])
    await message.answer("✅ Сохранено.", reply_markup=ReplyKeyboardRemove())
    await ask_dest_countries(message, state)

async def ask_dest_countries(message: Message, state: FSMContext):
    await message.answer(
        "Теперь введите **страны назначения** (коды через запятую).\n"
        "Или нажмите «Пропустить».",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    await state.set_state(FilterForm.dest_countries)

@router.message(FilterForm.dest_countries)
async def process_dest_countries(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏩ Пропустить":
        await state.update_data(dest_countries=[])
        await message.answer("✅ Пропущено.", reply_markup=ReplyKeyboardRemove())
        await ask_max_weight(message, state)
        return
    elif text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Настройка отменена.", reply_markup=ReplyKeyboardRemove())
        return
    
    if text:
        countries = [c.strip().upper() for c in text.split(',') if c.strip()]
        valid = [c for c in countries if re.match(r'^[A-Z]{2}$', c)]
        if not valid:
            await message.answer("❌ Неверный формат.")
            return
        await state.update_data(dest_countries=valid)
    else:
        await state.update_data(dest_countries=[])
    await message.answer("✅ Сохранено.", reply_markup=ReplyKeyboardRemove())
    await ask_max_weight(message, state)

async def ask_max_weight(message: Message, state: FSMContext):
    await message.answer(
        "Введите **максимальный вес** в килограммах (например, 900).\n"
        "Или нажмите «Пропустить».",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    await state.set_state(FilterForm.max_weight)

@router.message(FilterForm.max_weight)
async def process_max_weight(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏩ Пропустить":
        await state.update_data(max_weight_kg=None)
        await message.answer("✅ Пропущено.", reply_markup=ReplyKeyboardRemove())
        await ask_max_pallets(message, state)
        return
    elif text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Настройка отменена.", reply_markup=ReplyKeyboardRemove())
        return
    
    if text:
        try:
            val = float(text)
            if val < 0:
                raise ValueError
            await state.update_data(max_weight_kg=val)
        except ValueError:
            await message.answer("❌ Введите положительное число.")
            return
    else:
        await state.update_data(max_weight_kg=None)
    await message.answer("✅ Сохранено.", reply_markup=ReplyKeyboardRemove())
    await ask_max_pallets(message, state)

async def ask_max_pallets(message: Message, state: FSMContext):
    await message.answer(
        "Введите **максимальное количество паллет** (европаллеты 800×1200 мм, например, 3).\n"
        "Или нажмите «Пропустить».",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    await state.set_state(FilterForm.max_pallets)

@router.message(FilterForm.max_pallets)
async def process_max_pallets(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏩ Пропустить":
        await state.update_data(max_pallets=None)
        await message.answer("✅ Пропущено.", reply_markup=ReplyKeyboardRemove())
        await ask_min_price(message, state)
        return
    elif text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Настройка отменена.", reply_markup=ReplyKeyboardRemove())
        return
    
    if text:
        try:
            val = int(text)
            if val < 0:
                raise ValueError
            await state.update_data(max_pallets=val)
        except ValueError:
            await message.answer("❌ Введите целое положительное число.")
            return
    else:
        await state.update_data(max_pallets=None)
    await message.answer("✅ Сохранено.", reply_markup=ReplyKeyboardRemove())
    await ask_min_price(message, state)

async def ask_min_price(message: Message, state: FSMContext):
    await message.answer(
        "Введите **минимальную цену** в евро (например, 150).\n"
        "Или нажмите «Пропустить».",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    await state.set_state(FilterForm.min_price)

@router.message(FilterForm.min_price)
async def process_min_price(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏩ Пропустить":
        await state.update_data(min_price_eur=None)
        await message.answer("✅ Пропущено.", reply_markup=ReplyKeyboardRemove())
        await save_filter(message, state)
        return
    elif text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Настройка отменена.", reply_markup=ReplyKeyboardRemove())
        return
    
    if text:
        try:
            val = float(text)
            if val < 0:
                raise ValueError
            await state.update_data(min_price_eur=val)
        except ValueError:
            await message.answer("❌ Введите положительное число.")
            return
    else:
        await state.update_data(min_price_eur=None)
    await message.answer("✅ Сохранено.", reply_markup=ReplyKeyboardRemove())
    await save_filter(message, state)

async def save_filter(message: Message, state: FSMContext):
    data = await state.get_data()
    user_filter = {
        "origin_countries": data.get("origin_countries", []),
        "dest_countries": data.get("dest_countries", []),
        "max_weight_kg": data.get("max_weight_kg"),
        "max_pallets": data.get("max_pallets"),
        "min_price_eur": data.get("min_price_eur"),
    }
    user_id = message.from_user.id
    async with async_session() as session:
        stmt = select(UserFilter).where(UserFilter.user_id == user_id)
        result = await session.execute(stmt)
        uf = result.scalar_one_or_none()
        if uf:
            uf.filter_data = user_filter
        else:
            session.add(UserFilter(user_id=user_id, filter_data=user_filter))
        await session.commit()
    
    await message.answer(
        "✅ Фильтр сохранён!\n\n"
        f"📌 Страны отправления: {user_filter['origin_countries'] or 'любые'}\n"
        f"📌 Страны назначения: {user_filter['dest_countries'] or 'любые'}\n"
        f"📌 Макс. вес: {user_filter['max_weight_kg'] or 'не ограничен'} кг\n"
        f"📌 Макс. паллет: {user_filter['max_pallets'] or 'не ограничено'} (800×1200 мм)\n"
        f"📌 Мин. цена: {user_filter['min_price_eur'] or 'не задана'} €",
        parse_mode="Markdown"
    )
    await state.clear()

# ---- /view_filter ----
@router.message(Command("view_filter"))
async def cmd_view_filter(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        stmt = select(UserFilter).where(UserFilter.user_id == user_id)
        result = await session.execute(stmt)
        uf = result.scalar_one_or_none()
        if uf and uf.filter_data:
            f = uf.filter_data
            text = (
                "📋 **Текущий фильтр:**\n"
                f"• Страны отправления: {f.get('origin_countries') or 'любые'}\n"
                f"• Страны назначения: {f.get('dest_countries') or 'любые'}\n"
                f"• Макс. вес: {f.get('max_weight_kg') or 'не ограничен'} кг\n"
                f"• Макс. паллет: {f.get('max_pallets') or 'не ограничено'} (800×1200 мм)\n"
                f"• Мин. цена: {f.get('min_price_eur') or 'не задана'} €"
            )
            await message.answer(text, parse_mode="Markdown")
        else:
            await message.answer("📋 Фильтр не задан. Используй /set_filter.")

# ---- /reset_filter ----
@router.message(Command("reset_filter"))
async def cmd_reset_filter(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        stmt = select(UserFilter).where(UserFilter.user_id == user_id)
        result = await session.execute(stmt)
        uf = result.scalar_one_or_none()
        if uf:
            await session.delete(uf)
            await session.commit()
            await message.answer("🔄 Фильтр сброшен.")
        else:
            await message.answer("📋 Фильтр и так не задан.")

# ---- /pause и /resume ----
@router.message(Command("pause"))
async def cmd_pause(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        user = await session.get(User, user_id)
        if user:
            user.paused = True
            await session.commit()
    await message.answer("⏸️ Уведомления о заказах приостановлены. Фильтры сохранены.\nЧтобы возобновить, используй /resume.")

@router.message(Command("resume"))
async def cmd_resume(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        user = await session.get(User, user_id)
        if user:
            user.paused = False
            await session.commit()
    await message.answer("▶️ Уведомления о заказах возобновлены.")

# ---- /history ----
@router.message(Command("history"))
async def cmd_history(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    days = 2
    if len(args) > 1:
        try:
            days = int(args[1])
            if days < 1: days = 1
            if days > 7: days = 7
        except ValueError:
            pass
    
    orders = await get_orders_for_user(user_id, days)
    if not orders:
        await message.answer(f"📭 Нет заказов за последние {days} дней.")
        return
    
    async with async_session() as session:
        stmt = select(UserFilter).where(UserFilter.user_id == user_id)
        result = await session.execute(stmt)
        uf = result.scalar_one_or_none()
        user_filter = uf.filter_data if uf else {}
    
    from filters import match_filter
    filtered = []
    for o in orders:
        od = {"origin_country": o.origin_country, "dest_country": o.dest_country, "weight_kg": o.weight_kg, "pallets": o.pallets, "price_eur": o.price_eur}
        if match_filter(od, user_filter):
            filtered.append(o)
    
    if not filtered:
        await message.answer(f"📭 Заказов за {days} дней, подходящих под фильтр, нет.")
        return
    
    lines = [f"📋 **Заказы за {days} дней (под фильтр):**"]
    for idx, o in enumerate(filtered[:10], 1):
        lines.append(f"{idx}. {o.origin_city} → {o.dest_city}  |  {o.weight_kg} кг  |  {o.pallets or '?'} палл.  |  {o.price_eur} €  |  {o.platform}")
    if len(filtered) > 10:
        lines.append(f"... и ещё {len(filtered)-10}.")
    await message.answer("\n".join(lines), parse_mode="Markdown")

# ---- /stats ----
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        total = await session.scalar(select(func.count()).where(Order.user_id == user_id))
        if not total:
            await message.answer("📊 Нет данных по заказам.")
            return
        avg = await session.scalar(select(func.avg(Order.price_eur)).where(Order.user_id == user_id))
        avg = round(avg, 2) if avg else 0
        
        routes_res = await session.execute(
            select(Order.origin_city, Order.origin_country, Order.dest_city, Order.dest_country, func.count())
            .where(Order.user_id == user_id)
            .group_by(Order.origin_city, Order.origin_country, Order.dest_city, Order.dest_country)
            .order_by(func.count().desc())
            .limit(3)
        )
        routes = routes_res.all()
        route_lines = [f"• {r[0]},{r[1]} → {r[2]},{r[3]} – {r[4]} зак." for r in routes] if routes else ["• (нет данных)"]
        
        text = (
            "📊 **Статистика:**\n"
            f"• Всего заказов: {total}\n"
            f"• Средняя цена: {avg} €\n"
            "• Топ-3 маршрута:\n" + "\n".join(route_lines)
        )
        await message.answer(text, parse_mode="Markdown")

# ---- /favorites ----
@router.message(Command("favorites"))
async def cmd_favorites(message: Message):
    user_id = message.from_user.id
    favs = await get_favorites(user_id)
    if not favs:
        await message.answer("⭐ У вас нет избранных заказов.")
        return
    
    # Удаляем просроченные заказы из избранного
    now = datetime.utcnow()
    async with async_session() as session:
        for fav in favs:
            stmt = select(Order).where(
                Order.id == fav.order_id,
                Order.platform == fav.platform,
                Order.user_id == user_id
            )
            result = await session.execute(stmt)
            order = result.scalar_one_or_none()
            if order and order.deadline and order.deadline < now:
                await remove_favorite(user_id, order.id, order.platform)
        # Обновляем список
        favs = await get_favorites(user_id)
        if not favs:
            await message.answer("⭐ Все избранные заказы устарели и были удалены.")
            return
    
    orders = []
    async with async_session() as session:
        for f in favs:
            stmt = select(Order).where(Order.id == f.order_id, Order.platform == f.platform, Order.user_id == user_id)
            res = await session.execute(stmt)
            o = res.scalar_one_or_none()
            if o:
                orders.append((o, f.platform, f.order_id))
    
    if not orders:
        await message.answer("⭐ Избранные заказы не найдены (возможно, удалены).")
        return
    
    for order, platform, order_id in orders[:10]:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Взять заказ", callback_data=f"take_{platform}_{order_id}"),
                InlineKeyboardButton(text="❌ Удалить", callback_data=f"fav_del_{platform}_{order_id}")
            ]
        ])
        deadline_text = order.deadline.strftime('%d.%m.%Y %H:%M') if order.deadline else 'не указана'
        text = (f"⭐ {order.origin_city} → {order.dest_city}\n"
                f"⚖️ {order.weight_kg} кг | 💰 {order.price_eur} €\n"
                f"🆔 ID: {order_id}\n"
                f"⏳ Доставка до: {deadline_text}")
        await message.answer(text, reply_markup=keyboard)
    
    if len(orders) > 10:
        await message.answer(f"... и ещё {len(orders)-10} заказов в избранном.")

# ---- /favorite <id> ----
@router.message(Command("favorite"))
async def cmd_favorite(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите ID заказа. Пример: /favorite mock_0")
        return
    order_id = args[1].strip()
    user_id = message.from_user.id
    async with async_session() as session:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            await message.answer("❌ Заказ не найден.")
            return
        added = await add_favorite(user_id, order.id, order.platform)
        if added:
            await message.answer(f"⭐ Заказ {order_id} добавлен в избранное.")
        else:
            await message.answer(f"⭐ Заказ {order_id} уже в избранном.")

# ---- /unfavorite <id> ----
@router.message(Command("unfavorite"))
async def cmd_unfavorite(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите ID заказа. Пример: /unfavorite mock_0")
        return
    order_id = args[1].strip()
    user_id = message.from_user.id
    async with async_session() as session:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            await message.answer("❌ Заказ не найден.")
            return
        removed = await remove_favorite(user_id, order.id, order.platform)
        if removed:
            await message.answer(f"⭐ Заказ {order_id} удалён из избранного.")
        else:
            await message.answer(f"⭐ Заказ {order_id} не был в избранном.")

# ---- /accepted ----
@router.message(Command("accepted"))
async def cmd_accepted(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        stmt = select(AcceptedOrder).where(AcceptedOrder.user_id == user_id).order_by(AcceptedOrder.accepted_at.desc())
        result = await session.execute(stmt)
        accepted = result.scalars().all()
    if not accepted:
        await message.answer("📋 У вас нет принятых заказов.")
        return
    lines = ["📋 **Принятые заказы:**"]
    for idx, a in enumerate(accepted[:10], 1):
        lines.append(f"{idx}. Заказ {a.order_id} (платформа: {a.platform}) – принят {a.accepted_at.strftime('%d.%m.%Y %H:%M')}")
    if len(accepted) > 10:
        lines.append(f"... и ещё {len(accepted)-10}.")
    await message.answer("\n".join(lines), parse_mode="Markdown")

# ---- Обработчики callback для кнопок ----
@router.callback_query(lambda c: c.data.startswith("take_"))
async def callback_take_order(callback: CallbackQuery):
    data = callback.data.replace("take_", "").split("_", 1)
    if len(data) != 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    platform, order_id = data[0], data[1]
    user_id = callback.from_user.id
    
    # Проверяем, не принят ли уже
    async with async_session() as session:
        stmt = select(AcceptedOrder).where(
            AcceptedOrder.user_id == user_id,
            AcceptedOrder.order_id == order_id,
            AcceptedOrder.platform == platform
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            await callback.answer("⚠️ Заказ уже принят ранее.", show_alert=True)
            return
    
    await accept_order(user_id, order_id, platform)
    await callback.answer("✅ Заказ принят!", show_alert=False)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.edit_text(callback.message.text + "\n\n✅ **Принято!**")

@router.callback_query(lambda c: c.data.startswith("fav_del_"))
async def callback_fav_del(callback: CallbackQuery):
    data = callback.data.replace("fav_del_", "").split("_", 1)
    if len(data) != 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    platform, order_id = data[0], data[1]
    user_id = callback.from_user.id
    removed = await remove_favorite(user_id, order_id, platform)
    if removed:
        await callback.answer("⭐ Удалено из избранного!", show_alert=False)
        await callback.message.edit_text(callback.message.text + "\n\n❌ Удалено", reply_markup=None)
    else:
        await callback.answer("⏳ Не найдено", show_alert=False)

# ---- /help ----
@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 **Доступные команды:**\n\n"
        "/start – запуск бота и главное меню\n"
        "/set_filter – настроить фильтры (пошагово)\n"
        "/view_filter – показать текущие фильтры\n"
        "/reset_filter – сбросить фильтры\n"
        "/history [дни] – показать заказы за последние N дней (по умолчанию 2)\n"
        "/stats – статистика по заказам\n"
        "/favorites – показать избранные заказы\n"
        "/favorite <ID> – добавить заказ в избранное по ID\n"
        "/unfavorite <ID> – удалить заказ из избранного\n"
        "/accepted – принятые заказы\n"
        "/pause – приостановить уведомления\n"
        "/resume – возобновить уведомления\n"
        "/status – статус бота\n"
        "/help – эта справка\n"
        "/tutorial – подробное обучение\n"
        "/cancel – отменить настройку фильтра"
    )
    await message.answer(text, parse_mode="Markdown")

# ---- /tutorial ----
@router.message(Command("tutorial"))
async def cmd_tutorial(message: Message):
    text = (
        "📚 **Обучение: как пользоваться ботом**\n\n"
        "1. **Настройка фильтров** (`/set_filter`)\n"
        "   → Задай страны отправления и назначения, макс. вес, кол-во паллет (800×1200 мм) и мин. цену.\n"
        "   → Все параметры можно пропустить.\n\n"
        "2. **Получение заказов**\n"
        "   → Бот автоматически проверяет заказы каждую минуту.\n"
        "   → Подходящие заказы приходят с кнопками «Карта», «В избранное» и «Взять заказ».\n\n"
        "3. **Избранное** (`/favorites`)\n"
        "   → Сохраняй интересные заказы, чтобы вернуться к ним позже.\n"
        "   → В избранном есть кнопка «Взять заказ» и «Удалить».\n\n"
        "4. **Принятие заказов**\n"
        "   → Кнопка «Взять заказ» – заказ сохраняется в принятые и удаляется из избранного.\n\n"
        "5. **История** (`/history [дни]`)\n"
        "   → Показывает все заказы за указанное количество дней (по умолчанию 2).\n\n"
        "6. **Статистика** (`/stats`)\n"
        "   → Показывает общее количество заказов, среднюю цену и топ-3 маршрута.\n\n"
        "7. **Пауза** (`/pause`) и **Возобновить** (`/resume`)\n"
        "   → Останавливают и возобновляют уведомления без сброса фильтров.\n\n"
        "8. **Подсказка по кодам стран**\n"
        "   → NL – Нидерланды, BE – Бельгия, DE – Германия, FR – Франция,\n"
        "   → UK – Великобритания, IT – Италия, ES – Испания, PL – Польша, CZ – Чехия.\n\n"
        "9. **Важно**\n"
        "   → Бот работает 24/7. Ты можешь закрыть Telegram – уведомления всё равно придут.\n"
        "   → Если что-то не работает, проверь фильтры командой `/view_filter`."
    )
    await message.answer(text, parse_mode="Markdown")

# ---- /status ----
@router.message(Command("status"))
async def cmd_status(message: Message):
    await message.answer("✅ Бот активен. Сбор заказов происходит каждую минуту.")

# ---- /cancel ----
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("🤔 Нет активного диалога.")
    else:
        await state.clear()
        await message.answer("❌ Настройка отменена.", reply_markup=ReplyKeyboardRemove())
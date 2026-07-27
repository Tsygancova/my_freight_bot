from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from database import async_session, User, UserFilter, get_orders_for_user
from sqlalchemy import select
from database import add_favorite, remove_favorite, get_favorites, get_orders_for_user
from sqlalchemy import func, select
from database import Order, UserFilter
import re

router = Router()

# Состояния для пошагового ввода фильтров
class FilterForm(StatesGroup):
    origin_countries = State()
    dest_countries = State()
    max_weight = State()
    max_pallets = State()
    min_price = State()

# Клавиатура с кнопками "Пропустить" и "Отмена"
skip_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏩ Пропустить")],
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# ---------- Главное меню (Inline-кнопки) ----------
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="🔧 Настроить фильтры", callback_data="menu_set_filter")],
        [InlineKeyboardButton(text="📋 Показать фильтры", callback_data="menu_view_filter")],
        [InlineKeyboardButton(text="🔄 Сбросить фильтры", callback_data="menu_reset_filter")],
        [InlineKeyboardButton(text="📜 История заказов", callback_data="menu_history")],
        [InlineKeyboardButton(text="⭐ Избранное", callback_data="menu_favorites")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="menu_stats")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help")],
        [InlineKeyboardButton(text="📡 Статус", callback_data="menu_status")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------- /start ----------
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            session.add(User(id=user_id))
            await session.commit()
    await message.answer(
        "🚚 Привет! Я буду присылать мистеру котичке заказы.\n"
        "Используй меню ниже для управления ботом.\n"
        "Также доступны команды: /set_filter, /view_filter, /reset_filter, /history, /status",
        reply_markup=get_main_menu()
    )

# ---------- Обработчики callback-запросов от меню ----------
@router.callback_query(lambda c: c.data.startswith("menu_"))
async def process_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.replace("menu_", "")
    await callback.answer()  # убираем "часики"
    
    if action == "set_filter":
        await cmd_set_filter(callback.message, state)
    elif action == "view_filter":
        await cmd_view_filter(callback.message)
    elif action == "reset_filter":
        await cmd_reset_filter(callback.message)
    elif action == "history":
        await cmd_history(callback.message)
    elif action == "status":
        await cmd_status(callback.message)
    elif action == "favorites":
        await cmd_favorites(callback.message)
    elif action == "stats":
        await cmd_stats(callback.message)
    elif action == "help":
        await cmd_help(callback.message)

# ---------- Команда /set_filter ----------
@router.message(Command("set_filter"))
async def cmd_set_filter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Начинаем настройку фильтров.\n\n"
        "Введите **страны отправления** (коды через запятую, например: NL, BE, DE).\n"
        "Или нажмите кнопку «Пропустить», чтобы не ограничивать.",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    await state.set_state(FilterForm.origin_countries)

# ---------- Обработчик стран отправления ----------
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

# ---------- Обработчик стран назначения ----------
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

# ---------- Обработчик максимального веса ----------
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

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 **Доступные команды:**\n\n"
        "/start – запуск бота\n"
        "/set_filter – настроить фильтры (пошагово)\n"
        "/view_filter – показать текущие фильтры\n"
        "/reset_filter – сбросить фильтры\n"
        "/history [дни] – показать заказы за последние N дней\n"
        "/stats – статистика по заказам\n"
        "/favorites – показать избранные заказы\n"
        "/favorite <id> – добавить заказ в избранное (по ID)\n"
        "/unfavorite <id> – удалить из избранного\n"
        "/status – статус бота\n"
        "/help – эта справка"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        # Общее количество заказов для пользователя
        total_orders = await session.scalar(select(func.count()).where(Order.user_id == user_id))
        if not total_orders:
            await message.answer("📊 Нет данных по заказам.")
            return
        
        # Средняя цена
        avg_price = await session.scalar(select(func.avg(Order.price_eur)).where(Order.user_id == user_id))
        avg_price = round(avg_price, 2) if avg_price else 0
        
        # Топ-3 маршрутов (по паре город-страна отправления -> город-страна назначения)
        top_routes = await session.execute(
            select(Order.origin_city, Order.origin_country, Order.dest_city, Order.dest_country, func.count())
            .where(Order.user_id == user_id)
            .group_by(Order.origin_city, Order.origin_country, Order.dest_city, Order.dest_country)
            .order_by(func.count().desc())
            .limit(3)
        )
        routes = top_routes.all()
        route_lines = []
        for r in routes:
            route_lines.append(f"• {r[0]},{r[1]} → {r[2]},{r[3]} – {r[4]} заказов")
        
        text = (
            "📊 **Статистика заказов:**\n"
            f"• Всего заказов: {total_orders}\n"
            f"• Средняя цена: {avg_price} €\n"
            "• Топ-3 маршрута:\n" + "\n".join(route_lines) if route_lines else "• (нет данных)"
        )
        await message.answer(text, parse_mode="Markdown")

@router.message(Command("favorites"))
async def cmd_favorites(message: Message):
    user_id = message.from_user.id
    favs = await get_favorites(user_id)
    if not favs:
        await message.answer("⭐ У вас пока нет избранных заказов.")
        return
    
    # Получаем сами заказы из таблицы orders
    async with async_session() as session:
        order_ids = [(f.order_id, f.platform) for f in favs]
        # Собираем заказы по ID и платформе
        orders = []
        for oid, plat in order_ids:
            stmt = select(Order).where(Order.id == oid, Order.platform == plat, Order.user_id == user_id)
            result = await session.execute(stmt)
            order = result.scalar_one_or_none()
            if order:
                orders.append(order)
    
    if not orders:
        await message.answer("⭐ Избранные заказы не найдены (возможно, они уже удалены).")
        return
    
    lines = ["⭐ **Избранные заказы:**"]
    for idx, o in enumerate(orders[:10], 1):
        lines.append(
            f"{idx}. {o.origin_city} → {o.dest_city}  |  "
            f"{o.weight_kg} кг  |  {o.price_eur} €  |  {o.platform}  |  ID: {o.id}"
        )
    if len(orders) > 10:
        lines.append(f"... и ещё {len(orders)-10}.")
    await message.answer("\n".join(lines), parse_mode="Markdown")

@router.message(Command("favorite"))
async def cmd_favorite(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите ID заказа. Пример: /favorite mock_0")
        return
    order_id = args[1].strip()
    user_id = message.from_user.id
    # Ищем заказ в БД
    async with async_session() as session:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            await message.answer("❌ Заказ с таким ID не найден.")
            return
        added = await add_favorite(user_id, order.id, order.platform)
        if added:
            await message.answer(f"⭐ Заказ {order_id} добавлен в избранное.")
        else:
            await message.answer(f"⭐ Заказ {order_id} уже в избранном.")

@router.message(Command("unfavorite"))
async def cmd_unfavorite(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите ID заказа. Пример: /unfavorite mock_0")
        return
    order_id = args[1].strip()
    user_id = message.from_user.id
    # Ищем заказ
    async with async_session() as session:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            await message.answer("❌ Заказ с таким ID не найден.")
            return
        removed = await remove_favorite(user_id, order.id, order.platform)
        if removed:
            await message.answer(f"⭐ Заказ {order_id} удалён из избранного.")
        else:
            await message.answer(f"⭐ Заказ {order_id} не был в избранном.")

async def ask_max_pallets(message: Message, state: FSMContext):
    await message.answer(
        "Введите **максимальное количество паллет** (европаллеты 800×1200 мм, например, 3).\n"
        "Или нажмите «Пропустить».",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    await state.set_state(FilterForm.max_pallets)

# ---------- Обработчик количества паллет ----------
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

# ---------- Обработчик минимальной цены ----------
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
        "✅ Фильтр успешно сохранён!\n\n"
        f"📌 Страны отправления: {user_filter['origin_countries'] or 'любые'}\n"
        f"📌 Страны назначения: {user_filter['dest_countries'] or 'любые'}\n"
        f"📌 Макс. вес: {user_filter['max_weight_kg'] or 'не ограничен'} кг\n"
        f"📌 Макс. паллет: {user_filter['max_pallets'] or 'не ограничено'} (800×1200 мм)\n"
        f"📌 Мин. цена: {user_filter['min_price_eur'] or 'не задана'} €",
        parse_mode="Markdown"
    )
    await state.clear()

# ---------- /view_filter ----------
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
            await message.answer("📋 Фильтр не задан. Используй /set_filter, чтобы настроить.")

# ---------- /reset_filter ----------
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
            await message.answer("🔄 Фильтр сброшен. Теперь я буду присылать все заказы без ограничений.")
        else:
            await message.answer("📋 Фильтр и так не задан.")

# ---------- /history ----------
@router.message(Command("history"))
async def cmd_history(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    days = 2
    if len(args) > 1:
        try:
            days = int(args[1])
            if days < 1:
                days = 1
            if days > 7:
                days = 7
        except ValueError:
            pass
    
    orders = await get_orders_for_user(user_id, days)
    if not orders:
        await message.answer(f"📭 Нет заказов за последние {days} дней.")
        return
    
    # Получаем текущий фильтр
    async with async_session() as session:
        stmt = select(UserFilter).where(UserFilter.user_id == user_id)
        result = await session.execute(stmt)
        uf = result.scalar_one_or_none()
        user_filter = uf.filter_data if uf else {}
    
    from filters import match_filter
    filtered_orders = []
    for o in orders:
        order_dict = {
            "origin_country": o.origin_country,
            "origin_city": o.origin_city,
            "dest_country": o.dest_country,
            "dest_city": o.dest_city,
            "weight_kg": o.weight_kg,
            "pallets": o.pallets,
            "price_eur": o.price_eur,
        }
        if match_filter(order_dict, user_filter):
            filtered_orders.append(o)
    
    if not filtered_orders:
        await message.answer(f"📭 Заказов за последние {days} дней, подходящих под ваш фильтр, нет.")
        return
    
    lines = [f"📋 **Заказы за последние {days} дней (подходящие под фильтр):**"]
    for idx, o in enumerate(filtered_orders[:10], 1):
        lines.append(
            f"{idx}. {o.origin_city} → {o.dest_city}  |  "
            f"{o.weight_kg} кг  |  {o.pallets} палл.  |  {o.price_eur} €  |  {o.platform}"
        )
    if len(filtered_orders) > 10:
        lines.append(f"... и ещё {len(filtered_orders)-10} заказов.")
    await message.answer("\n".join(lines), parse_mode="Markdown")

# ---------- /status ----------
@router.message(Command("status"))
async def cmd_status(message: Message):
    await message.answer("✅ Бот активен. Сбор заказов происходит каждую минуту.")

# ---------- /cancel (отмена диалога) ----------
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("🤔 Нет активного диалога.")
    else:
        await state.clear()
        await message.answer("❌ Настройка отменена.", reply_markup=ReplyKeyboardRemove())

from aiogram.types import CallbackQuery

@router.callback_query(lambda c: c.data.startswith("fav_add_"))
async def callback_fav_add(callback: CallbackQuery):
    # формат: fav_add_{platform}_{order_id}
    data = callback.data.replace("fav_add_", "").split("_", 1)
    if len(data) != 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    platform, order_id = data[0], data[1]
    user_id = callback.from_user.id
    added = await add_favorite(user_id, order_id, platform)
    if added:
        await callback.answer("⭐ Добавлено в избранное!", show_alert=False)
    else:
        await callback.answer("⏳ Уже в избранном", show_alert=False)
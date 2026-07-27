from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from database import async_session, User, UserFilter, get_orders_for_user
from sqlalchemy import select
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
        [InlineKeyboardButton(text="ℹ️ Статус", callback_data="menu_status")],
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
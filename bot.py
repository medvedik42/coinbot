import logging
import asyncio
import random
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
API_TOKEN = '8489091168:AAGGhmhxErYWUXy_Kj5eYrVBVwVaN6HZBR8'

# БАЗА НА РАБОЧЕМ СТОЛЕ
desktop = Path.home() / "OneDrive" / "Desktop"
DATABASE_PATH = desktop / "coinz_bot.db"
logger.info(f"База данных: {DATABASE_PATH}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ========== БАЗА ДАННЫХ ==========
def get_db():
    conn = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_config (
        chat_id INTEGER PRIMARY KEY,
        coin_name TEXT DEFAULT 'КОИН',
        coin_price REAL DEFAULT 50.0,  -- ⭐ ДРОБНАЯ ЦЕНА ⭐
        farm_cooldown INTEGER DEFAULT 10,
        enable_level_limits INTEGER DEFAULT 1,
        enable_coin_limits INTEGER DEFAULT 1,
        max_coins_per_user INTEGER DEFAULT 100
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        username TEXT,
        first_name TEXT,
        balance REAL DEFAULT 0,
        farm_level INTEGER DEFAULT 1,
        passive_level INTEGER DEFAULT 0,
        last_farm_time TEXT,
        coin INTEGER DEFAULT 0,
        UNIQUE(user_id, chat_id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        passive_price REAL DEFAULT 10,
        farm_price REAL DEFAULT 10,
        UNIQUE(chat_id, user_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных создана")

# ========== УТИЛИТЫ ==========
def fmt(num):
    """Форматировать число с 2 знаками после запятой"""
    if isinstance(num, float):
        return f"{num:.2f}"
    return str(num)

def get_chat_config(chat_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM chat_config WHERE chat_id = ?', (chat_id,))
    config = cursor.fetchone()
    
    if not config:
        cursor.execute('INSERT INTO chat_config (chat_id) VALUES (?)', (chat_id,))
        conn.commit()
        cursor.execute('SELECT * FROM chat_config WHERE chat_id = ?', (chat_id,))
        config = cursor.fetchone()
    
    result = dict(config) if config else None
    conn.close()
    return result

def update_chat_config(chat_id, field, value):
    conn = get_db()
    cursor = conn.cursor()
    
    if field == 'coin_name':
        cursor.execute('UPDATE chat_config SET coin_name = ? WHERE chat_id = ?', (value, chat_id))
    elif field == 'coin_price':
        cursor.execute('UPDATE chat_config SET coin_price = ? WHERE chat_id = ?', (float(value), chat_id))
    elif field == 'farm_cooldown':
        cursor.execute('UPDATE chat_config SET farm_cooldown = ? WHERE chat_id = ?', (value, chat_id))
    elif field == 'enable_level_limits':
        cursor.execute('UPDATE chat_config SET enable_level_limits = ? WHERE chat_id = ?', (value, chat_id))
    elif field == 'enable_coin_limits':
        cursor.execute('UPDATE chat_config SET enable_coin_limits = ? WHERE chat_id = ?', (value, chat_id))
    elif field == 'max_coins_per_user':
        cursor.execute('UPDATE chat_config SET max_coins_per_user = ? WHERE chat_id = ?', (value, chat_id))
    
    conn.commit()
    conn.close()

def get_user(chat_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
    user = cursor.fetchone()
    
    result = dict(user) if user else None
    conn.close()
    return result

def save_user(user_data):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO users 
    (user_id, chat_id, username, first_name, balance, farm_level, passive_level, last_farm_time, coin)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_data['user_id'],
        user_data['chat_id'],
        user_data.get('username', ''),
        user_data.get('first_name', ''),
        user_data.get('balance', 0),
        user_data.get('farm_level', 1),
        user_data.get('passive_level', 0),
        user_data.get('last_farm_time'),
        user_data.get('coin', 0)
    ))
    
    conn.commit()
    conn.close()

def get_or_create_prices(chat_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM prices WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
    prices = cursor.fetchone()
    
    if not prices:
        cursor.execute('INSERT INTO prices (chat_id, user_id) VALUES (?, ?)', (chat_id, user_id))
        conn.commit()
        cursor.execute('SELECT * FROM prices WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
        prices = cursor.fetchone()
    
    result = dict(prices) if prices else None
    conn.close()
    return result

def update_user_field(chat_id, user_id, field, value):
    conn = get_db()
    cursor = conn.cursor()
    
    if field == 'balance':
        cursor.execute('UPDATE users SET balance = balance + ? WHERE chat_id = ? AND user_id = ?', 
                      (float(value), chat_id, user_id))
    elif field == 'coin':
        cursor.execute('UPDATE users SET coin = coin + ? WHERE chat_id = ? AND user_id = ?', 
                      (value, chat_id, user_id))
    elif field == 'farm_level':
        cursor.execute('UPDATE users SET farm_level = ? WHERE chat_id = ? AND user_id = ?', 
                      (value, chat_id, user_id))
    elif field == 'passive_level':
        cursor.execute('UPDATE users SET passive_level = ? WHERE chat_id = ? AND user_id = ?', 
                      (value, chat_id, user_id))
    elif field == 'last_farm_time':
        cursor.execute('UPDATE users SET last_farm_time = ? WHERE chat_id = ? AND user_id = ?', 
                      (value, chat_id, user_id))
    
    conn.commit()
    conn.close()

def update_price(chat_id, user_id, price_type, new_price):
    conn = get_db()
    cursor = conn.cursor()
    
    if price_type == 'passive':
        cursor.execute('UPDATE prices SET passive_price = ? WHERE chat_id = ? AND user_id = ?', 
                      (float(new_price), chat_id, user_id))
    elif price_type == 'farm':
        cursor.execute('UPDATE prices SET farm_price = ? WHERE chat_id = ? AND user_id = ?', 
                      (float(new_price), chat_id, user_id))
    
    conn.commit()
    conn.close()

# ========== НОВАЯ ФОРМУЛА ФАРМА ==========
def calculate_farm_reward(farm_level):
    base_min = farm_level * 0.01
    base_max = base_min + 0.05
    reward = random.uniform(base_min, base_max)
    return round(reward, 2)

# ========== ПРОВЕРКА АДМИНА ==========
async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Ошибка проверки админа: {e}")
        return False

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    user = get_user(chat_id, user_id)
    
    if not user:
        user_data = {
            'user_id': user_id,
            'chat_id': chat_id,
            'username': username,
            'first_name': first_name,
            'balance': 0,
            'farm_level': 1,
            'passive_level': 0,
            'coin': 0
        }
        save_user(user_data)
        get_or_create_prices(chat_id, user_id)
    
    config = get_chat_config(chat_id)
    admin_status = await is_admin(chat_id, user_id)
    
    text = f"🎉 <b>Добро пожаловать в Coinz, {first_name}!</b>\n\n"
    text += f"⭐ <b>Стартовый баланс: 0 монет</b>\n\n"
    text += f"📝 <b>Основные команды:</b>\n"
    text += f"• /balance - Баланс\n"
    text += f"• /farm - Собрать урожай\n"
    text += f"• /build - Магазин улучшений\n"
    text += f"• /trade @user N - Передать {config['coin_name']}\n"
    text += f"• /leaderboard - Топ игроков\n"
    text += f"• /profile - Профиль\n"
    text += f"• /help - Справка\n"
    
    if admin_status:
        text += f"\n⚙️ <b>Админ команды:</b>\n"
        text += f"• /set_price N - Цена {config['coin_name']} (текущая: {fmt(config['coin_price'])})\n"
        text += f"• /set_name название - Имя коина (текущее: {config['coin_name']})\n"
        text += f"• /set_cooldown N - Кулдаун фарма (текущий: {config['farm_cooldown']}ч)\n"
        text += f"• /set_max_coins N - Лимит коинов (текущий: {config['max_coins_per_user']})\n"
        text += f"• /addcoins @user N - Выдать монеты\n"
        text += f"• /level_limits - Вкл/выкл лимиты прокачки (сейчас: {'ВКЛ' if config['enable_level_limits'] else 'ВЫКЛ'})\n"
        text += f"• /coin_limits - Вкл/выкл лимиты коинов (сейчас: {'ВКЛ' if config['enable_coin_limits'] else 'ВЫКЛ'})\n"
    
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    
    if not user:
        await message.answer("❌ Сначала используйте /start")
        return
    
    text = (
        f"💰 <b>Ваш баланс:</b>\n\n"
        f"• Монеты: <b>{fmt(user['balance'])}</b>\n"
        f"• {config['coin_name']}: <b>{user['coin']}</b>"
    )
    
    if config['enable_coin_limits']:
        text += f" (макс: {config['max_coins_per_user']})"
    
    text += f"\n\n• Уровень фарма: <b>{user['farm_level']}</b>"
    
    if config['enable_level_limits']:
        text += " (макс: 20)"
    
    min_reward = user['farm_level'] * 0.01
    max_reward = min_reward + 0.05
    text += f"\n• Фарм: <b>{fmt(min_reward)}-{fmt(max_reward)}</b> монет"
    
    text += f"\n• Пассивный доход: <b>{user['passive_level']}/час</b>"
    
    if config['enable_level_limits']:
        text += " (макс: 20)"
    
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(Command("farm"))
async def cmd_farm(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    
    if not user:
        await message.answer("❌ Сначала используйте /start")
        return
    
    now = datetime.now()
    
    if user['last_farm_time']:
        last_time = datetime.fromisoformat(user['last_farm_time'])
        cooldown = timedelta(hours=config['farm_cooldown'])
        
        if now - last_time < cooldown:
            time_left = cooldown - (now - last_time)
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            await message.answer(f"⏳ Следующий сбор через {hours}ч {minutes}м")
            return
    
    earned = calculate_farm_reward(user['farm_level'])
    update_user_field(chat_id, user_id, 'balance', earned)
    update_user_field(chat_id, user_id, 'last_farm_time', now.isoformat())
    
    user = get_user(chat_id, user_id)
    
    min_reward = user['farm_level'] * 0.01
    max_reward = min_reward + 0.05
    
    text = (
        f"🌾 <b>Урожай собран!</b>\n\n"
        f"• Получено: <b>{fmt(earned)}</b> монет\n"
        f"• Новый баланс: <b>{fmt(user['balance'])}</b>\n"
        f"• Уровень фарма: <b>{user['farm_level']}</b>\n"
        f"• Диапазон фарма: <b>{fmt(min_reward)}-{fmt(max_reward)}</b> монет"
    )
    
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(Command("build"))
async def cmd_build(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    
    if not user:
        await message.answer("❌ Сначала используйте /start")
        return
    
    prices = get_or_create_prices(chat_id, user_id)
    
    max_level = 20 if config['enable_level_limits'] else 999
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"⚡ Пассивка (Ур.{user['passive_level']}/{max_level}) - {fmt(prices['passive_price'])}",
                callback_data="buy_passive"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🌾 Фарм (Ур.{user['farm_level']}/{max_level}) - {fmt(prices['farm_price'])}",
                callback_data="buy_farm"
            )
        ],
        [
            InlineKeyboardButton(text=f"💎 Купить {config['coin_name']} ({fmt(config['coin_price'])})", callback_data="buy_coin"),
            InlineKeyboardButton(text=f"💎 Продать {config['coin_name']} ({fmt(config['coin_price'])})", callback_data="sell_coin")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_shop"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
        ]
    ])
    
    level_limit_status = "ВКЛ" if config['enable_level_limits'] else "ВЫКЛ"
    coin_limit_status = "ВКЛ" if config['enable_coin_limits'] else "ВЫКЛ"
    max_coins_info = f" (макс: {config['max_coins_per_user']})" if config['enable_coin_limits'] else ""
    
    min_reward = user['farm_level'] * 0.01
    max_reward = min_reward + 0.05
    
    text = (
        f"🛒 <b>Магазин улучшений</b>\n\n"
        f"• Баланс: <b>{fmt(user['balance'])}</b>\n"
        f"• {config['coin_name']}: <b>{user['coin']}{max_coins_info}</b>\n\n"
        f"• Уровень фарма: <b>{user['farm_level']}/{max_level}</b>\n"
        f"• Фарм: <b>{fmt(min_reward)}-{fmt(max_reward)}</b> монет\n"
        f"• Пассивный доход: <b>{user['passive_level']}/{max_level}</b>\n\n"
        f"⚙️ <b>Настройки:</b>\n"
        f"• Лимиты прокачки: <b>{level_limit_status}</b>\n"
        f"• Лимиты коинов: <b>{coin_limit_status}</b>"
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# ========== ОБРАБОТЧИКИ КНОПОК ==========
@router.callback_query(F.data == "close")
async def callback_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()

@router.callback_query(F.data == "refresh_shop")
async def callback_refresh_shop(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    prices = get_or_create_prices(chat_id, user_id)
    
    max_level = 20 if config['enable_level_limits'] else 999
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"⚡ Пассивка (Ур.{user['passive_level']}/{max_level}) - {fmt(prices['passive_price'])}",
                callback_data="buy_passive"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🌾 Фарм (Ур.{user['farm_level']}/{max_level}) - {fmt(prices['farm_price'])}",
                callback_data="buy_farm"
            )
        ],
        [
            InlineKeyboardButton(text=f"💎 Купить {config['coin_name']} ({fmt(config['coin_price'])})", callback_data="buy_coin"),
            InlineKeyboardButton(text=f"💎 Продать {config['coin_name']} ({fmt(config['coin_price'])})", callback_data="sell_coin")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_shop"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
        ]
    ])
    
    level_limit_status = "ВКЛ" if config['enable_level_limits'] else "ВЫКЛ"
    coin_limit_status = "ВКЛ" if config['enable_coin_limits'] else "ВЫКЛ"
    max_coins_info = f" (макс: {config['max_coins_per_user']})" if config['enable_coin_limits'] else ""
    
    min_reward = user['farm_level'] * 0.01
    max_reward = min_reward + 0.05
    
    text = (
        f"🛒 <b>Магазин улучшений</b>\n\n"
        f"• Баланс: <b>{fmt(user['balance'])}</b>\n"
        f"• {config['coin_name']}: <b>{user['coin']}{max_coins_info}</b>\n\n"
        f"• Уровень фарма: <b>{user['farm_level']}/{max_level}</b>\n"
        f"• Фарм: <b>{fmt(min_reward)}-{fmt(max_reward)}</b> монет\n"
        f"• Пассивный доход: <b>{user['passive_level']}/{max_level}</b>\n\n"
        f"⚙️ <b>Настройки:</b>\n"
        f"• Лимиты прокачки: <b>{level_limit_status}</b>\n"
        f"• Лимиты коинов: <b>{coin_limit_status}</b>"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer("✅ Магазин обновлен!")

@router.callback_query(F.data == "buy_passive")
async def callback_buy_passive(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    prices = get_or_create_prices(chat_id, user_id)
    
    if not user or not prices:
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    max_level = 20 if config['enable_level_limits'] else 999
    
    if user['passive_level'] >= max_level:
        await callback.answer(f"❌ Максимальный уровень {max_level}!", show_alert=True)
        return
    
    if user['balance'] < prices['passive_price']:
        await callback.answer(f"❌ Недостаточно средств! Нужно: {fmt(prices['passive_price'])}", show_alert=True)
        return
    
    update_user_field(chat_id, user_id, 'balance', -prices['passive_price'])
    update_user_field(chat_id, user_id, 'passive_level', user['passive_level'] + 1)
    update_price(chat_id, user_id, 'passive', prices['passive_price'] * 2)
    
    await callback.answer(f"✅ Пассивный доход повышен до уровня {user['passive_level'] + 1}!", show_alert=True)
    await callback_refresh_shop(callback)

@router.callback_query(F.data == "buy_farm")
async def callback_buy_farm(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    prices = get_or_create_prices(chat_id, user_id)
    
    if not user or not prices:
        await callback.answer("❌ Ошибка данных!", show_alert=True)
        return
    
    max_level = 20 if config['enable_level_limits'] else 999
    
    if user['farm_level'] >= max_level:
        await callback.answer(f"❌ Максимальный уровень {max_level}!", show_alert=True)
        return
    
    if user['balance'] < prices['farm_price']:
        await callback.answer(f"❌ Недостаточно средств! Нужно: {fmt(prices['farm_price'])}", show_alert=True)
        return
    
    update_user_field(chat_id, user_id, 'balance', -prices['farm_price'])
    update_user_field(chat_id, user_id, 'farm_level', user['farm_level'] + 1)
    update_price(chat_id, user_id, 'farm', prices['farm_price'] * 2)
    
    await callback.answer(f"✅ Уровень фарма повышен до {user['farm_level'] + 1}!", show_alert=True)
    await callback_refresh_shop(callback)

@router.callback_query(F.data == "buy_coin")
async def callback_buy_coin(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    if config['enable_coin_limits'] and user['coin'] >= config['max_coins_per_user']:
        await callback.answer(f"❌ Достигнут лимит коинов! Максимум: {config['max_coins_per_user']}", show_alert=True)
        return
    
    if user['balance'] < config['coin_price']:
        await callback.answer(f"❌ Недостаточно средств! Нужно: {fmt(config['coin_price'])}", show_alert=True)
        return
    
    update_user_field(chat_id, user_id, 'balance', -config['coin_price'])
    update_user_field(chat_id, user_id, 'coin', 1)
    
    await callback.answer(f"✅ Куплен 1 {config['coin_name']} за {fmt(config['coin_price'])} монет!", show_alert=True)
    await callback_refresh_shop(callback)

@router.callback_query(F.data == "sell_coin")
async def callback_sell_coin(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    if user['coin'] < 1:
        await callback.answer(f"❌ У вас нет {config['coin_name']}!", show_alert=True)
        return
    
    update_user_field(chat_id, user_id, 'balance', config['coin_price'])
    update_user_field(chat_id, user_id, 'coin', -1)
    
    await callback.answer(f"✅ Продан 1 {config['coin_name']} за {fmt(config['coin_price'])} монет!", show_alert=True)
    await callback_refresh_shop(callback)

@router.message(Command("trade"))
async def cmd_trade(message: Message):
    chat_id = message.chat.id
    args = message.text.split()
    
    if len(args) != 3:
        config = get_chat_config(chat_id)
        await message.answer(f"💎 <b>Передача {config['coin_name']}</b>\n\nФормат: /trade @username количество\nПример: /trade @user123 5")
        return
    
    target_username = args[1]
    
    try:
        amount = int(args[2])
        if amount <= 0:
            await message.answer("❌ Количество должно быть больше 0!")
            return
    except ValueError:
        await message.answer("❌ Неверное количество!")
        return
    
    sender_id = message.from_user.id
    
    sender = get_user(chat_id, sender_id)
    if not sender:
        await message.answer("❌ Сначала используйте /start")
        return
    
    config = get_chat_config(chat_id)
    
    if sender['coin'] < amount:
        await message.answer(f"❌ Недостаточно {config['coin_name']}! У вас: {sender['coin']}")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    if target_username.startswith('@'):
        username = target_username[1:]
    else:
        username = target_username
    
    cursor.execute('SELECT user_id, first_name FROM users WHERE username = ? AND chat_id = ?', (username, chat_id))
    receiver = cursor.fetchone()
    
    if not receiver:
        conn.close()
        await message.answer("❌ Пользователь не найден!")
        return
    
    receiver_id = receiver['user_id']
    receiver_name = receiver['first_name'] or username
    
    if sender_id == receiver_id:
        conn.close()
        await message.answer("❌ Нельзя передавать самому себе!")
        return
    
    receiver_data = get_user(chat_id, receiver_id)
    if config['enable_coin_limits'] and receiver_data['coin'] + amount > config['max_coins_per_user']:
        conn.close()
        await message.answer(f"❌ У получателя будет превышен лимит коинов! Максимум: {config['max_coins_per_user']}")
        return
    
    update_user_field(chat_id, sender_id, 'coin', -amount)
    update_user_field(chat_id, receiver_id, 'coin', amount)
    
    await message.answer(f"✅ Передано {amount} {config['coin_name']} пользователю {receiver_name}")

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    chat_id = message.chat.id
    config = get_chat_config(chat_id)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        CASE 
            WHEN first_name IS NOT NULL AND first_name != '' THEN first_name
            WHEN username IS NOT NULL AND username != '' THEN '@' || username
            ELSE 'Игрок'
        END as display_name,
        balance 
    FROM users 
    WHERE chat_id = ? 
    ORDER BY balance DESC 
    LIMIT 10
    ''', (chat_id,))
    coins_top = cursor.fetchall()
    
    cursor.execute('''
    SELECT 
        CASE 
            WHEN first_name IS NOT NULL AND first_name != '' THEN first_name
            WHEN username IS NOT NULL AND username != '' THEN '@' || username
            ELSE 'Игрок'
        END as display_name,
        coin 
    FROM users 
    WHERE chat_id = ? 
    ORDER BY coin DESC 
    LIMIT 10
    ''', (chat_id,))
    coin_top = cursor.fetchall()
    
    conn.close()
    
    text = "🏆 <b>Топ игроков</b>\n\n"
    
    text += "💰 <b>По монетам:</b>\n"
    for i, user in enumerate(coins_top, 1):
        text += f"{i}. {user['display_name']} - {fmt(user['balance'])}\n"
    
    text += f"\n💎 <b>По {config['coin_name']}:</b>\n"
    for i, user in enumerate(coin_top, 1):
        text += f"{i}. {user['display_name']} - {user['coin']}\n"
    
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    config = get_chat_config(chat_id)
    user = get_user(chat_id, user_id)
    
    if not user:
        await message.answer("❌ Сначала используйте /start")
        return
    
    display_name = user['first_name'] or user['username'] or f"Игрок {user_id}"
    
    text = (
        f"👤 <b>Профиль {display_name}</b>\n\n"
        f"• Монеты: <b>{fmt(user['balance'])}</b>\n"
        f"• {config['coin_name']}: <b>{user['coin']}</b>"
    )
    
    if config['enable_coin_limits']:
        text += f" (макс: {config['max_coins_per_user']})"
    
    text += f"\n\n• Уровень фарма: <b>{user['farm_level']}</b>"
    
    if config['enable_level_limits']:
        text += " (макс: 20)"
    
    min_reward = user['farm_level'] * 0.01
    max_reward = min_reward + 0.05
    text += f"\n• Фарм: <b>{fmt(min_reward)}-{fmt(max_reward)}</b> монет"
    
    text += f"\n• Пассивный доход: <b>{user['passive_level']}/час</b>"
    
    if config['enable_level_limits']:
        text += " (макс: 20)"
    
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    config = get_chat_config(chat_id)
    admin_status = await is_admin(chat_id, user_id)
    
    text = "📚 <b>Основные команды:</b>\n\n"
    text += "• /start - Начать игру\n"
    text += "• /balance - Баланс\n"
    text += "• /farm - Собрать урожай\n"
    text += "• /build - Магазин улучшений\n"
    text += f"• /trade @user N - Передать {config['coin_name']}\n"
    text += "• /leaderboard - Топ игроков\n"
    text += "• /profile - Профиль\n"
    text += "• /help - Справка\n"
    
    if admin_status:
        text += "\n⚙️ <b>Админ команды:</b>\n"
        text += f"• /set_price N - Цена {config['coin_name']}\n"
        text += f"• /set_name название - Имя коина\n"
        text += "• /set_cooldown N - Кулдаун фарма\n"
        text += "• /set_max_coins N - Лимит коинов на игрока\n"
        text += "• /addcoins @user N - Выдать монеты\n"
        text += "• /level_limits - Вкл/выкл лимиты прокачки\n"
        text += "• /coin_limits - Вкл/выкл лимиты коинов\n"
    
    await message.answer(text, parse_mode=ParseMode.HTML)

# ========== АДМИН КОМАНДЫ ==========
@router.message(Command("set_price"))
async def cmd_set_price(message: Message, command: CommandObject):
    chat_id = message.chat.id
    
    if not await is_admin(chat_id, message.from_user.id):
        await message.answer("❌ Эта команда только для админов!")
        return
    
    args = command.args
    if not args:
        config = get_chat_config(chat_id)
        await message.answer(f"❌ Формат: /set_price [цена]\nТекущая цена: {fmt(config['coin_price'])}")
        return
    
    try:
        # ⭐ ПРИНИМАЕМ ДРОБНЫЕ ЧИСЛА ⭐
        price = float(args.replace(',', '.'))  # Поддержка запятой и точки
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return
        
        if price > 1000000:
            await message.answer("❌ Максимальная цена 1,000,000")
            return
        
        update_chat_config(chat_id, 'coin_price', price)
        
        config = get_chat_config(chat_id)
        await message.answer(f"✅ Цена {config['coin_name']} изменена на <b>{fmt(price)}</b> монет", parse_mode=ParseMode.HTML)
        
    except ValueError:
        await message.answer("❌ Введите число (можно дробное, например: 50.5 или 50,5)")

@router.message(Command("set_name"))
async def cmd_set_name(message: Message, command: CommandObject):
    chat_id = message.chat.id
    
    if not await is_admin(chat_id, message.from_user.id):
        await message.answer("❌ Эта команда только для админов!")
        return
    
    args = command.args
    if not args:
        config = get_chat_config(chat_id)
        await message.answer(f"❌ Формат: /set_name [название]\nТекущее название: {config['coin_name']}")
        return
    
    name = args.strip()
    if len(name) > 20:
        await message.answer("❌ Слишком длинное название (макс. 20 символов)")
        return
    
    update_chat_config(chat_id, 'coin_name', name)
    
    await message.answer(f"✅ Название коина изменено на '<b>{name}</b>'", parse_mode=ParseMode.HTML)

@router.message(Command("set_cooldown"))
async def cmd_set_cooldown(message: Message, command: CommandObject):
    chat_id = message.chat.id
    
    if not await is_admin(chat_id, message.from_user.id):
        await message.answer("❌ Эта команда только для админов!")
        return
    
    args = command.args
    if not args:
        config = get_chat_config(chat_id)
        await message.answer(f"❌ Формат: /set_cooldown [часы]\nТекущий кулдаун: {config['farm_cooldown']}ч")
        return
    
    try:
        cooldown = int(args)
        if cooldown < 1:
            await message.answer("❌ Кулдаун должен быть больше 0 часов")
            return
        
        if cooldown > 168:
            await message.answer("❌ Максимум 168 часов (1 неделя)")
            return
        
        update_chat_config(chat_id, 'farm_cooldown', cooldown)
        
        await message.answer(f"✅ Кулдаун фарма изменен на <b>{cooldown}</b> часов", parse_mode=ParseMode.HTML)
        
    except ValueError:
        await message.answer("❌ Введите целое число")

@router.message(Command("set_max_coins"))
async def cmd_set_max_coins(message: Message, command: CommandObject):
    chat_id = message.chat.id
    
    if not await is_admin(chat_id, message.from_user.id):
        await message.answer("❌ Эта команда только для админов!")
        return
    
    args = command.args
    if not args:
        config = get_chat_config(chat_id)
        await message.answer(f"❌ Формат: /set_max_coins [количество]\nТекущий лимит: {config['max_coins_per_user']}")
        return
    
    try:
        max_coins = int(args)
        if max_coins < 1:
            await message.answer("❌ Лимит должен быть больше 0")
            return
        
        if max_coins > 1000000:
            await message.answer("❌ Максимум 1,000,000 коинов")
            return
        
        update_chat_config(chat_id, 'max_coins_per_user', max_coins)
        
        config = get_chat_config(chat_id)
        await message.answer(f"✅ Лимит коинов изменен на <b>{max_coins}</b> на игрока", parse_mode=ParseMode.HTML)
        
    except ValueError:
        await message.answer("❌ Введите целое число")

@router.message(Command("addcoins"))
async def cmd_addcoins(message: Message, command: CommandObject):
    chat_id = message.chat.id
    
    if not await is_admin(chat_id, message.from_user.id):
        await message.answer("❌ Эта команда только для админов!")
        return
    
    args = command.args
    if not args:
        await message.answer("❌ Формат: /addcoins @username количество")
        return
    
    parts = args.split()
    if len(parts) != 2:
        await message.answer("❌ Формат: /addcoins @username количество")
        return
    
    username = parts[0]
    
    try:
        amount = float(parts[1].replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Количество должно быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверное количество")
        return
    
    if not username.startswith('@'):
        await message.answer("❌ Укажите @username")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, first_name FROM users WHERE username = ? AND chat_id = ?', 
                  (username[1:], chat_id))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        await message.answer("❌ Пользователь не найден")
        return
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND chat_id = ?',
                  (amount, user['user_id'], chat_id))
    
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Выдано {fmt(amount)} монет пользователю {username}")

@router.message(Command("level_limits"))
async def cmd_level_limits(message: Message):
    chat_id = message.chat.id
    
    if not await is_admin(chat_id, message.from_user.id):
        await message.answer("❌ Эта команда только для админов!")
        return
    
    config = get_chat_config(chat_id)
    
    new_state = 0 if config['enable_level_limits'] else 1
    update_chat_config(chat_id, 'enable_level_limits', new_state)
    
    status = "ВКЛЮЧЕНЫ" if new_state else "ВЫКЛЮЧЕНЫ"
    max_level = "20" if new_state else "нет лимита"
    
    await message.answer(f"✅ Лимиты прокачки <b>{status}</b>\nМакс. уровень улучшений: <b>{max_level}</b>", parse_mode=ParseMode.HTML)

@router.message(Command("coin_limits"))
async def cmd_coin_limits(message: Message):
    chat_id = message.chat.id
    
    if not await is_admin(chat_id, message.from_user.id):
        await message.answer("❌ Эта команда только для админов!")
        return
    
    config = get_chat_config(chat_id)
    
    new_state = 0 if config['enable_coin_limits'] else 1
    update_chat_config(chat_id, 'enable_coin_limits', new_state)
    
    status = "ВКЛЮЧЕНЫ" if new_state else "ВЫКЛЮЧЕНЫ"
    limit_info = f"\nМакс. коинов на игрока: <b>{config['max_coins_per_user']}</b>" if new_state else ""
    
    await message.answer(f"✅ Лимиты коинов <b>{status}</b>{limit_info}", parse_mode=ParseMode.HTML)

# ========== ЗАПУСК ==========
async def main():
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот запущен: @{me.username}")
        
        init_database()
        
        logger.info("🚀 Запускаю polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
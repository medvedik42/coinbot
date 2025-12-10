import logging
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import random

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# ========== НАСТРОЙКИ ==========
API_TOKEN = os.getenv('BOT_TOKEN', '8489091168:AAGGhmhxErYWUXy_Kj5eYrVBVwVaN6HZBR8')

# БАЗА В ТЕКУЩЕЙ ДИРЕКТОРИИ (Render)
DATABASE_PATH = os.path.join(os.getcwd(), "coinz_bot.db")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"База данных: {DATABASE_PATH}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ========== WEBHOOK НАСТРОЙКИ ==========
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = "my-secret"  # опционально для безопасности
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 10000

async def on_startup(bot: Bot):
    # Получаем URL из переменной окружения Render
    webhook_url = os.getenv('RENDER_EXTERNAL_URL', '') + WEBHOOK_PATH
    
    if webhook_url:
        await bot.set_webhook(webhook_url, secret_token=WEBHOOK_SECRET)
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    else:
        logger.error("❌ RENDER_EXTERNAL_URL не установлен!")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logger.info("❌ Webhook удален")

# ========== ВАШ СУЩЕСТВУЮЩИЙ КОД ==========
# (весь ваш текущий код функций, БД, команд и т.д.)
# ... init_database(), get_db(), cmd_start(), cmd_farm(), и т.д. ...
# НИЖЕ ПРИВЕДЕНА ТОЛЬКО ЧАСТЬ КОДА ДЛЯ ПРИМЕРА:

def init_database():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0
    )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ База данных создана")

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Я бот Coinz! 🎉")

# ... остальной ваш код ...

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
def main():
    # Инициализация базы
    init_database()
    
    # Создаем aiohttp приложение
    app = web.Application()
    
    # Настраиваем webhook handler
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET
    )
    
    # Регистрируем webhook endpoint
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Настраиваем startup/shutdown
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Запускаем приложение
    logger.info(f"🚀 Запускаю сервер на {WEBAPP_HOST}:{WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()
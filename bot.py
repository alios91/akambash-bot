import os
import json
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")  # например: https://akambash.onrender.com

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Загружаем словарь ---
with open("akambash_dict.json", "r", encoding="utf-8") as f:
    dictionary = json.load(f)

# --- /start ---
@dp.message(commands=["start"])
async def start_handler(message: Message):
    await message.answer(
        f"Салам, {message.from_user.first_name}! 🌿\n"
        f"Я — Akambash, твой наставник в мире абхазского языка.\n"
        f"Напиши слово на русском, и я покажу его перевод на абхазский и турецкий."
    )

# --- /help ---
@dp.message(commands=["help"])
async def help_handler(message: Message):
    await message.answer(
        "📚 Доступные команды:\n"
        "/start — приветствие\n"
        "/help — помощь\n"
        "Напиши слово на русском — я покажу перевод."
    )

# --- Перевод слов ---
@dp.message()
async def translate_handler(message: Message):
    text = message.text.strip().lower()
    for entry in dictionary:
        if entry["ru"].lower() == text:
            await message.answer(
                f"🇷🇺 **{entry['ru']}**\n"
                f"🇹🇷 {entry['tr']}\n"
                f"🇦🇲 {entry['ab']}\n"
                f"🔤 {entry['lat']}"
            )
            return
    await message.answer("❌ Слово не найдено в словаре.")

# --- Webhook ---
async def on_startup(app: web.Application):
    await bot.set_webhook(f"{BASE_URL}/{BOT_TOKEN}")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=f"/{BOT_TOKEN}")
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

if __name__ == "__main__":
    main()

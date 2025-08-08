import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан! Установите переменную окружения BOT_TOKEN.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(commands=["start"])
async def cmd_start(message: Message):
    await message.answer("Салам! Бот с вебхуком готов к работе.")

@dp.message()
async def echo(message: Message):
    await message.answer(f"Эхо: {message.text}")

async def on_startup():
    if not BASE_URL:
        raise ValueError("❌ BASE_URL не задан! Установите переменную окружения BASE_URL.")
    webhook_url = f"{BASE_URL}/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)
    print(f"✅ Вебхук установлен: {webhook_url}")

async def init_app():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=f"/{BOT_TOKEN}")
    await on_startup()
    return app

if __name__ == "__main__":
    web.run_app(init_app(), host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

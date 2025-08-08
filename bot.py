import os
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")

if not BOT_TOKEN or not BASE_URL:
    raise ValueError("❌ BOT_TOKEN или BASE_URL не заданы в Environment Variables на Render!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(commands=["start"])
async def start(message: types.Message):
    await message.answer("Салам! ✅ Бот с вебхуком на Render работает.")

@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Эхо: {message.text}")

async def on_startup(app):
    webhook_url = f"{BASE_URL}/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)
    print(f"✅ Вебхук установлен: {webhook_url}")

async def on_shutdown(app):
    await bot.delete_webhook()

app = web.Application()
SimpleRequestHandler(dp, bot).register(app, path=f"/{BOT_TOKEN}")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")  # например: https://akambash-bot.onrender.com

if not BOT_TOKEN or not BASE_URL:
    raise ValueError("❌ BOT_TOKEN или BASE_URL не заданы в Environment Variables на Render!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Я Akambash Bot и готов помогать!")

# Обработчик любого текста
@dp.message(F.text)
async def echo_handler(message: Message):
    await message.answer(f"Вы написали: {message.text}")

# Настройка вебхука
async def on_startup(app: web.Application):
    webhook_url = f"{BASE_URL}/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook установлен: {webhook_url}")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await bot.session.close()

# HTTP сервер
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

app = web.Application()
app.router.add_post(f'/{BOT_TOKEN}', handle)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

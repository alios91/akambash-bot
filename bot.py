# bot.py — webhook, подключает akambash_extra (поддержка words.json и fallback на akambash_dict.json)
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from akambash_extra import install as install_akambash_extra

BOT_TOKEN    = os.getenv("BOT_TOKEN")
BASE_URL     = os.getenv("BASE_URL")               # напр. https://your-app.onrender.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
PORT         = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN не задан")
if not BASE_URL:
    raise SystemExit("BASE_URL не задан (публичный HTTPS-домен)")

WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

async def app_factory() -> web.Application:
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # подключаем новые хендлеры (язык/кнопка/слова)
    install_akambash_extra(dp)

    # настраиваем вебхук
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

    app = web.Application()
    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app

if __name__ == "__main__":
    web.run_app(app_factory(), host="0.0.0.0", port=PORT)


# bot.py — webhook + онлайн‑перевод через Glosbe, aiogram 3.x
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from akambash_extra import router  # включает /start, кнопки, а также /tr и авто‑перевод

TOKEN = os.getenv("BOT_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "")  # например, https://akambash-bot.onrender.com
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH if BASE_URL else None

async def app_factory():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not WEBHOOK_URL:
        raise RuntimeError("BASE_URL is not set; can't build WEBHOOK_URL")

    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

    app = web.Application()
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # health endpoint
    async def health(request):
        return web.json_response({"ok": True})
    app.router.add_get("/health", health)

    return app

if __name__ == "__main__":
    web.run_app(app_factory(), host="0.0.0.0", port=PORT)

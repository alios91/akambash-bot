
# bot.py — PRODUCTION, stable structure for Akambash Bot (Webhook on Render)
# Features:
# - Healthcheck:        GET /health
# - Direct Glosbe test: GET /test_glosbe?q=море
# - Webhook endpoint:   POST /webhook
# - Optional local run without Telegram API: SKIP_WEBHOOK=1
# - Pluggable routers: akambash_extra.router (+ optionally custom routers)
#
# ENV:
#   BOT_TOKEN   — Telegram bot token (required in production)
#   BASE_URL    — public base URL, e.g. https://akambash-bot.onrender.com (required in production)
#   PORT        — provided by Render; default 8080 for local
#   SKIP_WEBHOOK=1 — run without Telegram API (local diagnostics)
#   APP_VERSION — optional; reported at /version
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Core Akambash router (start, buttons, word card, /tr, auto-translate)
from akambash_extra import router as akambash_router, translate_to_abkhaz

# Optionally include your extra routers without breaking if files are absent.
OPTIONAL_ROUTERS = []
for mod_name, attr in [
    ("routes_custom", "router"),
    ("routes_quiz", "router"),
    ("routes_admin", "router"),
]:
    try:
        module = __import__(mod_name, fromlist=[attr])
        OPTIONAL_ROUTERS.append(getattr(module, attr))
    except Exception:
        pass

TOKEN = os.getenv("BOT_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "")
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = (BASE_URL + WEBHOOK_PATH) if BASE_URL else None
SKIP_WEBHOOK = os.getenv("SKIP_WEBHOOK", "0") == "1"
APP_VERSION = os.getenv("APP_VERSION", "dev")

async def app_factory():
    app = web.Application()

    # --- Diagnostics ---
    async def health(_):
        return web.json_response({"ok": True, "version": APP_VERSION})
    app.router.add_get("/health", health)

    async def version(_):
        return web.json_response({"version": APP_VERSION})
    app.router.add_get("/version", version)

    # Quick Glosbe check without Telegram (useful both locally and on Render)
    async def test_glosbe(request):
        q = (request.query.get("q") or "").strip()
        if not q:
            return web.json_response({"ok": False, "error": "missing q"}, status=400)
        try:
            data = await translate_to_abkhaz(q)
            return web.json_response({"ok": True, "data": data})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)
    app.router.add_get("/test_glosbe", test_glosbe)

    # --- Telegram webhook wiring ---
    if not SKIP_WEBHOOK:
        if not TOKEN:
            raise RuntimeError("BOT_TOKEN is not set")
        if not WEBHOOK_URL:
            raise RuntimeError("BASE_URL is not set; can't build WEBHOOK_URL")

        bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        # include Akambash core router first
        dp.include_router(akambash_router)
        # include any extra routers if present
        for r in OPTIONAL_ROUTERS:
            dp.include_router(r)

        # set webhook
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

        # attach webhook app
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

    return app

if __name__ == "__main__":
    web.run_app(app_factory(), host="0.0.0.0", port=PORT)


# bot.py — webhook + автоперевод → абхазский (SCII), aiogram 3.x
# Если у тебя уже были свои хэндлеры — добавь их рядом и/или включи свои роутеры.
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# наши функции: онлайн-перевод → AB и SCII
from akambash_extra import translate_to_abkhaz, scii_translit

# autodetect языка сообщения
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    HAS_LANGDETECT = True
except Exception:
    HAS_LANGDETECT = False

BOT_TOKEN    = os.getenv("BOT_TOKEN")
BASE_URL     = os.getenv("BASE_URL")                 # напр. https://your-app.onrender.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
PORT         = int(os.getenv("PORT", "8080"))
WEBHOOK_URL  = (BASE_URL.rstrip("/") + WEBHOOK_PATH) if BASE_URL else None

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# ===== Простая память языка интерфейса (замени на БД при желании) =====
USER_LANG: dict[int, str] = {}  # user_id -> RU|EN|TR
LANG_BUTTONS = [("RU", "Русский"), ("EN", "English"), ("TR", "Türkçe")]
LANG_UI_TO_SRC = {"RU": "ru", "EN": "en", "TR": "tr"}

def kb_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=title, callback_data=f"lang:{code}")
    ] for code, title in LANG_BUTTONS])

main_router = Router(name="main")

@main_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Выбери язык интерфейса / Choose your UI language / Arayüz dilini seç:", reply_markup=kb_lang())

@main_router.callback_query(F.data.startswith("lang:"))
async def cb_lang(callback: CallbackQuery):
    code = callback.data.split(":", 1)[1].upper()
    USER_LANG[callback.from_user.id] = code
    heads = {"RU": "Готово! Язык интерфейса: Русский", "EN":"Done! UI language: English", "TR":"Tamam! Arayüz dili: Türkçe"}
    await callback.message.answer(heads.get(code, "Done."))
    await callback.answer()

@main_router.message(Command("setlang"))
async def cmd_setlang(message: Message, command: CommandObject):
    # /setlang RU|EN|TR
    arg = (command.args or "").strip().upper()
    if arg not in {"RU","EN","TR"}:
        return await message.answer("Пример: /setlang RU (или EN / TR)")
    USER_LANG[message.from_user.id] = arg
    await message.answer(f"Язык интерфейса обновлён: {arg}")

def get_user_lang(user_id: int) -> str:
    # Можно заменить на вызов БД: get_user(user_id).lang_ui
    return USER_LANG.get(user_id, "RU")

# ===== Автоперевод → Абхазский (любой ввод пользователя) =====
auto_router = Router(name="auto_translate")

@auto_router.message(Command("test_glosbe"))
async def cmd_test_glosbe(message: Message, command: CommandObject):
    query = (command.args or "").strip() or "ekmek"
    lang_ui = get_user_lang(message.from_user.id)

    if HAS_LANGDETECT:
        try:
            src = detect(query) or LANG_UI_TO_SRC.get(lang_ui, "ru")
        except Exception:
            src = LANG_UI_TO_SRC.get(lang_ui, "ru")
    else:
        src = LANG_UI_TO_SRC.get(lang_ui, "ru")

    found = await translate_to_abkhaz(query, src=src)
    if not found:
        texts = {
            "RU": "Не нашёл перевод на абхазский 😕 Попробуй другое слово.",
            "EN": "Couldn't find Abkhaz translation 😕 Try another word.",
            "TR": "Abhazca çeviri bulunamadı 😕 Başka bir kelime deneyin."
        }
        return await message.answer(texts.get(lang_ui, texts["RU"]))

    heads = {"RU": "🌐 Перевод (тест)", "EN": "🌐 Translation (test)", "TR": "🌐 Çeviri (test)"}
    await message.answer(f"{heads.get(lang_ui, heads['RU'])}:\n{src.upper()}: {query}\nAB: {found['ab']}\nLAT: {found['lat']}")

@auto_router.message(F.text & ~F.text.startswith(('/', '@', 'http')))
async def auto_translate_any_text(message: Message):
    query = (message.text or "").strip()
    if not query:
        return

    lang_ui = get_user_lang(message.from_user.id)

    # Если уже абхазский — просто LAT
    abkh_letters = "әӘԥҦҵҴҳҲӡӠқҚҕҟҞҭҬҩҶџЏҽҼ"
    if any(ch in query for ch in abkh_letters):
        lat = scii_translit(query)
        heads = {"RU": "📚 Абхазский → LAT", "EN": "📚 Abkhaz → LAT", "TR": "📚 Abhazca → LAT"}
        return await message.answer(f"{heads.get(lang_ui, heads['RU'])}:\nAB: {query}\nLAT: {lat}")

    if HAS_LANGDETECT:
        try:
            src = detect(query) or LANG_UI_TO_SRC.get(lang_ui, "ru")
        except Exception:
            src = LANG_UI_TO_SRC.get(lang_ui, "ru")
    else:
        src = LANG_UI_TO_SRC.get(lang_ui, "ru")

    found = await translate_to_abkhaz(query, src=src)
    if not found:
        texts = {
            "RU": "Не нашёл перевод на абхазский 😕 Попробуй проще/короче.",
            "EN": "Couldn't find Abkhaz translation 😕 Try simpler/shorter.",
            "TR": "Abhazca çeviri bulunamadı 😕 Daha basit/kısa deneyin."
        }
        return await message.answer(texts.get(lang_ui, texts["RU"]))

    heads = {"RU":"🌐 Перевод","EN":"🌐 Translation","TR":"🌐 Çeviri"}
    await message.answer(f"{heads.get(lang_ui, heads['RU'])}:\n{src.upper()}: {query}\nAB: {found['ab']}\nLAT: {found['lat']}")

# ====== Запуск webhook ======
async def app_factory():
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp  = Dispatcher()
    dp.include_router(main_router)
    dp.include_router(auto_router)

    if not WEBHOOK_URL:
        raise RuntimeError("BASE_URL is not set; can't build WEBHOOK_URL")
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

    app = web.Application()
    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app

if __name__ == "__main__":
    web.run_app(app_factory(), host="0.0.0.0", port=PORT)

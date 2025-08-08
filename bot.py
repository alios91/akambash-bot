import json
import random
import os
import logging
import asyncio
from datetime import datetime, time

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")

if not BOT_TOKEN or not BASE_URL:
    raise ValueError("❌ BOT_TOKEN или BASE_URL не заданы в Environment Variables на Render!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Загружаем слова из JSON
with open("words.json", "r", encoding="utf-8") as f:
    WORDS = json.load(f)

user_settings = {}  # user_id: {"lang": "ru", "autosend": True, "used_words": set()}

lang_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Русский"), KeyboardButton(text="English"), KeyboardButton(text="Türkçe")]
    ],
    resize_keyboard=True
)

yes_no_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Выбери язык для изучения:", reply_markup=lang_kb)

@dp.message(F.text.in_(["Русский", "English", "Türkçe"]))
async def choose_language(message: Message):
    lang_map = {
        "Русский": "ru",
        "English": "en",
        "Türkçe": "tr"
    }
    user_settings[message.from_user.id] = {
        "lang": lang_map[message.text],
        "autosend": False,
        "used_words": set()
    }
    await message.answer("Хотите получать слова 5 раз в день до 18:00 и пожелание спокойной ночи в 21:00?",
                         reply_markup=yes_no_kb)

@dp.message(F.text.in_(["Да", "Нет"]))
async def set_autosend(message: Message):
    if message.from_user.id not in user_settings:
        await message.answer("Сначала выберите язык через /start.")
        return

    if message.text == "Да":
        user_settings[message.from_user.id]["autosend"] = True
        await message.answer("Отлично! Буду присылать слова в течение дня.")
    else:
        user_settings[message.from_user.id]["autosend"] = False
        await message.answer("Хорошо, не буду присылать автоматически.")

@dp.message(F.text)
async def echo_handler(message: Message):
    await message.answer(f"Вы написали: {message.text}")

def get_random_word(user_id):
    lang = user_settings[user_id]["lang"]
    used = user_settings[user_id]["used_words"]

    available = [w for w in WORDS[lang] if w[lang] not in used]

    if not available:  # если закончились слова, обнуляем
        used.clear()
        available = WORDS[lang]

    word = random.choice(available)
    used.add(word[lang])
    return f"{word.get(lang)} — {word.get('ab')}"

async def scheduled_words():
    send_times = [time(9, 0), time(11, 0), time(13, 0), time(15, 0), time(17, 0)]
    night_time = time(21, 0)

    while True:
        now = datetime.now().time()

        for uid, settings in user_settings.items():
            if settings["autosend"]:
                for st in send_times:
                    if now.hour == st.hour and now.minute == st.minute:
                        try:
                            await bot.send_message(uid, f"📚 Новое слово: {get_random_word(uid)}")
                        except Exception as e:
                            logging.error(f"Ошибка при отправке слова {uid}: {e}")

                if now.hour == night_time.hour and now.minute == night_time.minute:
                    try:
                        await bot.send_message(uid, "🌙 Спокойной ночи!")
                    except Exception as e:
                        logging.error(f"Ошибка при отправке ночного сообщения {uid}: {e}")

        await asyncio.sleep(60)

async def on_startup(app: web.Application):
    webhook_url = f"{BASE_URL}/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook установлен: {webhook_url}")
    asyncio.create_task(scheduled_words())

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await bot.session.close()

async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def health(request):
    return web.Response(text="✅ Bot is running")

app = web.Application()
app.router.add_post(f'/{BOT_TOKEN}', handle)
app.router.add_get("/", health)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

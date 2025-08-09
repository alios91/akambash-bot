# akambash_extra.py — основной роутер Akambash + онлайн-перевод через Glosbe

from __future__ import annotations

# ===== aiogram / UI =====
import asyncio
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

router = Router(name="akambash_extra")

# ===== Базовые хэндлеры UI =====
@router.message(Command("start"))
async def cmd_start(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Слово")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    await message.answer(
        "Добро пожаловать в Akambash! Нажми «Слово» или пришли текст для перевода.",
        reply_markup=kb
    )

@router.message(F.text.in_(["Слово", "Word", "Kelime"]))
async def handle_new_word(message: Message):
    await message.answer("Чтобы проверить перевод, используй: /tr море")

def more_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➡️ Ещё слово", callback_data="word:more")]]
    )

@router.callback_query(F.data == "word:more")
async def more_word(cb: CallbackQuery):
    await cb.message.answer("Ещё слово — в разработке. Сейчас попробуй /tr море")
    await cb.answer()

# ===== Glosbe переводчик (усиленный) =====
from collections import deque
import html, re, json as _json
import aiohttp
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0

AK_GLOSBE_LOG = deque(maxlen=20)  # мини-лог попыток

GL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.9,tr;q=0.7",
    "Referer": "https://glosbe.com/",
    "Connection": "keep-alive",
}

def _aklog(**kwargs):
    AK_GLOSBE_LOG.append(kwargs)

def detect_lang(text: str) -> str:
    try:
        code = detect(text)
    except Exception:
        return "ru"
    return {"ru": "ru", "en": "en", "tr": "tr", "ab": "ab"}.get(code, "ru")

# Заглушка SCII — подставь свою реализацию при готовности
def scii_translit(ab_text: str) -> str:
    return ab_text

async def _gl_fetch(session: aiohttp.ClientSession, url: str) -> str:
    last_err = None
    for attempt in range(4):
        try:
            async with session.get(
                url, headers=GL_HEADERS, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=12)
            ) as r:
                text = await r.text()
                if r.status == 200 and text:
                    return text
                last_err = f"HTTP {r.status}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        await asyncio.sleep(0.7 * (attempt + 1))
    _aklog(stage="fetch_fail", url=url, error=last_err)
    return ""

def _gl_extract_next_data(html_text: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>',
                  html_text, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return {}
    try:

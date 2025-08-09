# akambash_extra.py — основной роутер Akambash + онлайн-перевод через Glosbe
from __future__ import annotations

# ===== aiogram / UI =====
import asyncio, html, re, json as _json
from collections import deque
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
    return {"ru":"ru","en":"en","tr":"tr","ab":"ab"}.get(code, "ru")

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
        return _json.loads(html.unescape(m.group(1)))
    except Exception as e:
        _aklog(stage="next_data_parse_error", error=str(e))
        return {}

def _gl_pull_translations_from_next(next_data: dict) -> list[str]:
    found: list[str] = []
    def walk(node):
        if isinstance(node, dict):
            for k in ("displayTranslations", "translation", "translations"):
                if k in node and isinstance(node[k], list):
                    for item in node[k]:
                        if isinstance(item, dict):
                            val = item.get("displayText") or item.get("text") or item.get("phrase")
                            if isinstance(val, str):
                                v = val.strip()
                                if v:
                                    found.append(v)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(next_data)
    seen, uniq = set(), []
    for w in found:
        if w not in seen:
            seen.add(w); uniq.append(w)
    return uniq

def _gl_pull_translations_from_html(html_text: str) -> list[str]:
    # лёгкий HTML-fallback, если структура Glosbe изменится
    candidates = re.findall(
        r'(?:class="[^"]*translation[^"]*"[^>]*>|data-testid="translation"[^>]*>)([^<]{1,80})</',
        html_text, flags=re.IGNORECASE
    )
    cleaned, seen = [], set()
    for c in candidates:
        v = html.unescape(c).strip()
        if v and v not in seen:
            seen.add(v); cleaned.append(v)
    return cleaned

async def glosbe_translate(term: str, src: str, dst: str = "ab") -> dict:
    src = {"ru":"ru","en":"en","tr":"tr","ab":"ab"}.get(src, "ru")
    dst = {"ru":"ru","en":"en","tr":"tr","ab":"ab"}.get(dst, "ab")
    url = f"https://glosbe.com/{src}/{dst}/{term}"
    _aklog(stage="start", url=url, term=term, src=src, dst=dst)
    async with aiohttp.ClientSession() as session:
        html_text = await _gl_fetch(session, url)
    if not html_text:
        return {"src": src, "dst": dst, "term": term, "translations": [], "primary": ""}

    next_data = _gl_extract_next_data(html_text)
    translations = _gl_pull_translations_from_next(next_data) if next_data else []
    if not translations:
        translations = _gl_pull_translations_from_html(html_text)
        if translations:
            _aklog(stage="fallback_html", count=len(translations))

    primary = translations[0] if translations else ""
    return {"src": src, "dst": dst, "term": term, "translations": translations, "primary": primary}

async def translate_to_abkhaz(text: str) -> dict:
    src = detect_lang(text)
    res = await glosbe_translate(text, src=src, dst="ab")
    ab = res.get("primary") or ""
    lat = scii_translit(ab) if ab else ""
    out = {"src": src, "query": text, "ab": ab, "lat": lat, "variants": res.get("translations", [])[:5]}
    if not ab:
        _aklog(stage="no_primary", query=text, variants=out["variants"])
    return out

# ===== Хэндлеры перевода =====
@router.message(Command("tr"))
async def tr_cmd(message: Message, command: CommandObject):
    text = (command.args or "").strip()
    if not text:
        await message.answer("Пришли слово или фразу после команды: `/tr море`", parse_mode=ParseMode.MARKDOWN)
        return
    data = await translate_to_abkhaz(text)
    if not data.get("ab"):
        await message.answer("Не нашёл перевод на Glosbe. Попробуй другое слово.")
        return
    variants = ", ".join(data.get("variants", []))
    await message.answer(
        f"<b>AB:</b> {data['ab']}\n<b>LAT:</b> {data['lat']}\n\nВарианты: {variants}",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text.len() > 0)
async def tr_auto(message: Message):
    text = message.text.strip()
    data = await translate_to_abkhaz(text)
    if data.get("ab"):
        await message.answer(f"{data['ab']} — {data['lat']}")

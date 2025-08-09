# akambash_extra.py
# Добавляет:
# - /start: выбор RU/EN/TR + сразу первое слово
# - reply-кнопку: слово / word / kelime
# - /new и кнопка -> карточка AB + LAT + RU + TR
# - инлайн «➡️ Ещё слово»
from __future__ import annotations
import asyncio, html, re, json as _json
import aiohttp
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0
import json, random
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

# --- словарь: сначала words.json, если нет — akambash_dict.json ---
PRIMARY_DICT = Path("words.json")
FALLBACK_DICT = Path("akambash_dict.json")

def _dict_path() -> Path:
    if PRIMARY_DICT.exists():
        return PRIMARY_DICT
    return FALLBACK_DICT

# --- конфиг кнопок ---
LABELS = {
    "RU": {"word_btn": "слово", "placeholder": "Нажми — слово"},
    "EN": {"word_btn": "word",  "placeholder": "Tap — word"},
    "TR": {"word_btn": "kelime","placeholder": "Bas — kelime"},
}
WORD_TEXTS = {"слово", "word", "kelime"}

def main_kb(lang: str | None) -> ReplyKeyboardMarkup:
    lang = (lang or "RU").upper()
    lbl = LABELS.get(lang, LABELS["RU"])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lbl["word_btn"])]],
        resize_keyboard=True,
        input_field_placeholder=lbl["placeholder"],
    )

# --- кэш словаря + анти-повтор ---
_USER_LANG: dict[int, str] = {}
_RECENT: dict[int, list[int]] = {}
_dict_cache: list[dict] | None = None

def load_dict() -> list[dict]:
    global _dict_cache
    if _dict_cache is None:
        p = _dict_path()
        if not p.exists():
            # создадим пустую заготовку, чтобы бот не падал
            p.write_text("[]", encoding="utf-8")
        _dict_cache = json.loads(p.read_text(encoding="utf-8"))
        for i, row in enumerate(_dict_cache):
            row.setdefault("id", i)
    return _dict_cache

def _pick_index(user_id: int, pool: int) -> int:
    recent = set(_RECENT.get(user_id, []))
    for _ in range(200):
        idx = random.randrange(pool)
        if idx not in recent:
            _RECENT.setdefault(user_id, []).append(idx)
            _RECENT[user_id] = _RECENT[user_id][-50:]
            return idx
    return 0

def build_word_text(entry: dict) -> str:
    ab  = entry.get("ab", "")
    lat = entry.get("lat", "")
    ru  = entry.get("ru", "")
    tr  = entry.get("tr") or "—"
    return (
        "📚 <b>Новое слово</b>\n\n"
        f"<b>AB:</b> {ab}\n"
        f"<b>LAT:</b> {lat}\n"
        f"<b>RU:</b> {ru}\n"
        f"<b>TR:</b> {tr}"
    )

def more_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➡️ Ещё слово", callback_data="word:more")]]
    )

router = Router(name="akambash_extra")

async def send_new_word(message: Message) -> None:
    data = load_dict()
    if not data:
        await message.answer("Словарь пуст. Добавь записи в words.json или akambash_dict.json")
        return
    idx = _pick_index(message.from_user.id, len(data))
    entry = data[idx]
    await message.answer(build_word_text(entry), reply_markup=more_keyboard(), parse_mode="HTML")

@router.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Русский", callback_data="lang:RU")],
        [InlineKeyboardButton(text="English", callback_data="lang:EN")],
        [InlineKeyboardButton(text="Türkçe",  callback_data="lang:TR")],
    ])
    await message.answer("Привет! Выбери язык интерфейса:", reply_markup=kb)

@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(callback: CallbackQuery):
    code = callback.data.split(":", 1)[1]
    _USER_LANG[callback.from_user.id] = code
    await callback.message.answer("Клавиатура настроена.", reply_markup=main_kb(code))
    await send_new_word(callback.message)
    await callback.answer()

@router.message(Command("new"))
async def cmd_new(message: Message):
    await send_new_word(message)

@router.message(F.text.func(lambda s: s and s.strip().lower() in WORD_TEXTS))
async def on_word_button(message: Message):
    await send_new_word(message)

@router.callback_query(F.data == "word:more")
async def cb_more(callback: CallbackQuery):
    if callback.message:
        await send_new_word(callback.message)
    await callback.answer()

def install(dp):
    # Подключение роутера из этого файла
    dp.include_router(router)


def scii_translit(ab_text: str) -> str:
    # TODO: replace with your real SCII transliteration
    return ab_text


def detect_lang(text: str) -> str:
    try:
        code = detect(text)
    except Exception:
        return 'ru'
    return {'ru':'ru','en':'en','tr':'tr'}.get(code, 'ru')


GL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

async def _gl_fetch(session: aiohttp.ClientSession, url: str) -> str:
    for attempt in range(3):
        try:
            async with session.get(url, headers=GL_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
                r.raise_for_status()
                return await r.text()
        except Exception:
            await asyncio.sleep(0.6 * (attempt + 1))
    return ""

def _gl_extract_next_data(html_text: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html_text, flags=re.DOTALL|re.IGNORECASE)
    if not m:
        return {}
    try:
        return _json.loads(html.unescape(m.group(1)))
    except Exception:
        return {}

def _gl_pull_translations(next_data: dict) -> list[str]:
    found = []
    def walk(node):
        if isinstance(node, dict):
            for k in ("displayTranslations", "translation", "translations"):
                if k in node and isinstance(node[k], list):
                    for item in node[k]:
                        if isinstance(item, dict):
                            val = item.get("displayText") or item.get("text") or item.get("phrase")
                            if isinstance(val, str):
                                val = val.strip()
                                if val:
                                    found.append(val)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(next_data)
    # unique preserve order
    seen, uniq = set(), []
    for w in found:
        if w not in seen:
            seen.add(w); uniq.append(w)
    return uniq

async def glosbe_translate(term: str, src: str, dst: str = "ab") -> dict:
    src = {"ru":"ru","en":"en","tr":"tr","ab":"ab"}.get(src, "ru")
    dst = {"ru":"ru","en":"en","tr":"tr","ab":"ab"}.get(dst, "ab")
    url = f"https://glosbe.com/{src}/{dst}/{term}"
    async with aiohttp.ClientSession() as session:
        html_text = await _gl_fetch(session, url)
    next_data = _gl_extract_next_data(html_text)
    translations = _gl_pull_translations(next_data)
    return {"src": src, "dst": dst, "term": term, "translations": translations, "primary": (translations[0] if translations else "")}

async def translate_to_abkhaz(text: str) -> dict:
    src = detect_lang(text)
    res = await glosbe_translate(text, src=src, dst="ab")
    ab = res.get("primary") or ""
    lat = scii_translit(ab) if ab else ""
    return {"src": src, "query": text, "ab": ab, "lat": lat, "variants": res.get("translations", [])[:5]}



from aiogram.enums import ParseMode
from aiogram.filters import CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(Command("tr"))
async def tr_cmd(message: Message, command: CommandObject):
    text = (command.args or "").strip()
    if not text:
        await message.answer("Пришли слово или фразу после команды: `/tr море`", parse_mode="Markdown")
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


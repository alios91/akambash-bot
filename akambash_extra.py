# akambash_extra.py
# Добавляет:
# - /start: выбор RU/EN/TR + сразу первое слово
# - reply-кнопку: слово / word / kelime
# - /new и кнопка -> карточка AB + LAT + RU + TR
# - инлайн «➡️ Ещё слово»
from __future__ import annotations
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

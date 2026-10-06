import os
import sqlite3
from contextlib import closing
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
WEBHOOK_BASE = os.environ.get("WEBHOOK_BASE", "").strip().rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not WEBHOOK_BASE:
    raise RuntimeError("WEBHOOK_BASE is missing")

DB = "zex_shop.db"
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = WEBHOOK_BASE + WEBHOOK_PATH

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

def db():
    return sqlite3.connect(DB)

def init_db():
    with closing(db()) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                balance REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()

def save_user(user: types.User):
    with closing(db()) as con:
        con.execute("""
            INSERT OR IGNORE INTO users
            (user_id, username, first_name, balance)
            VALUES (?, ?, ?, 0)
        """, (user.id, user.username or "", user.first_name or ""))
        con.execute("""
            UPDATE users SET username=?, first_name=? WHERE user_id=?
        """, (user.username or "", user.first_name or "", user.id))
        con.commit()

def keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎟 PROMOKOD"), KeyboardButton(text="👤 PROFIL")],
            [KeyboardButton(text="🧮 GOLD HISOBLASH"), KeyboardButton(text="🛒 GOLD SOTIB OLISH")],
            [KeyboardButton(text="💳 PUL KIRITISH")]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def start(message: types.Message):
    save_user(message.from_user)
    await message.answer(
        "👋 ZEX SHOP ga xush kelibsiz!\n\n"
        "🪙 Standoff 2 Gold xizmatlari uchun kerakli bo‘limni tanlang 👇",
        reply_markup=keyboard()
    )

@dp.message()
async def menu_handler(message: types.Message):
    save_user(message.from_user)
    t = message.text or ""

    if t == "👤 PROFIL":
        with closing(db()) as con:
            row = con.execute(
                "SELECT balance FROM users WHERE user_id=?",
                (message.from_user.id,)
            ).fetchone()
        balance = float(row[0]) if row else 0
        await message.answer(
            f"👤 PROFIL\n\n🆔 ID: {message.from_user.id}\n💰 Balans: {balance:g} so'm"
        )

    elif t == "💳 PUL KIRITISH":
        await message.answer("💳 Pul kiritish uchun: @lwox_org")

    elif t == "🎟 PROMOKOD":
        await message.answer("🎟 Promokod bo‘limi.")

    elif t == "🧮 GOLD HISOBLASH":
        await message.answer("🧮 Gold hisoblash bo‘limi.")

    elif t == "🛒 GOLD SOTIB OLISH":
        await message.answer(
            "🛒 Gold sotib olish uchun admin bilan bog‘laning."
        )

    else:
        await message.answer("Menyudan bo‘limni tanlang 👇", reply_markup=keyboard())

@app.get("/")
async def root():
    return {"status": "ZEX SHOP is running", "webhook": WEBHOOK_URL}

@app.get("/health")
async def health():
    return {"ok": True}

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update.model_validate(data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        print("WEBHOOK ERROR:", repr(e), flush=True)
        return {"ok": False}

@app.on_event("startup")
async def startup():
    init_db()
    try:
        info = await bot.get_me()
        print(f"BOT CONNECTED: @{info.username} ({info.id})", flush=True)
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.set_webhook(
            WEBHOOK_URL,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False
        )
        webhook_info = await bot.get_webhook_info()
        print(
            f"WEBHOOK SET: {webhook_info.url} | "
            f"pending={webhook_info.pending_update_count}",
            flush=True
        )
    except Exception as e:
        print("STARTUP ERROR:", repr(e), flush=True)

@app.on_event("shutdown")
async def shutdown():
    await bot.session.close()

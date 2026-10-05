import os
import sqlite3
from contextlib import closing
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "").strip().rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")
if not WEBHOOK_BASE:
    raise RuntimeError("WEBHOOK_BASE environment variable is required")

DB = "zex_shop.db"
app = FastAPI()
dp = Dispatcher()
bot = Bot(BOT_TOKEN)

def init_db():
    with closing(sqlite3.connect(DB)) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        con.commit()

def ensure_user(u):
    with closing(sqlite3.connect(DB)) as con:
        con.execute("""
        INSERT OR IGNORE INTO users(user_id, username, first_name)
        VALUES(?,?,?)
        """, (u.id, u.username or "", u.first_name or ""))
        con.commit()

def menu():
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
    ensure_user(message.from_user)
    await message.answer(
        "👋 ZEX SHOP ga xush kelibsiz!\n\n"
        "🪙 Standoff 2 Gold xizmatlari uchun menyudan foydalaning.",
        reply_markup=menu()
    )

@dp.message()
async def all_messages(message: types.Message):
    ensure_user(message.from_user)
    text = message.text or ""

    if text == "👤 PROFIL":
        with closing(sqlite3.connect(DB)) as con:
            row = con.execute(
                "SELECT balance FROM users WHERE user_id=?", (message.from_user.id,)
            ).fetchone()
        balance = row[0] if row else 0
        await message.answer(
            f"👤 Profil\n\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"💰 Balans: {balance:g} so'm"
        )

    elif text == "💳 PUL KIRITISH":
        await message.answer("💳 Pul kiritish uchun: @lwox_org")

    elif text == "🎟 PROMOKOD":
        await message.answer("🎟 Promokod bo‘limi tez orada ishlaydi.")

    elif text == "🧮 GOLD HISOBLASH":
        await message.answer("🧮 Gold hisoblash bo‘limi tez orada ishlaydi.")

    elif text == "🛒 GOLD SOTIB OLISH":
        await message.answer(
            "🛒 Gold sotib olish uchun buyurtma yuboring.\n"
            "Admin siz bilan bog‘lanadi."
        )

    else:
        await message.answer("Menyudan kerakli bo‘limni tanlang 👇", reply_markup=menu())

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"status": "ZEX SHOP is running"}

@app.on_event("startup")
async def startup():
    init_db()
    await bot.set_webhook(f"{WEBHOOK_BASE}/webhook")

@app.on_event("shutdown")
async def shutdown():
    await bot.delete_webhook()
    await bot.session.close()

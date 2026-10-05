import os
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import closing

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
PAYMENT_USERNAME = os.getenv("PAYMENT_USERNAME", "lwox_org").strip().lstrip("@")
GOLD_RATE = int(os.getenv("GOLD_RATE", "105"))
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "lwox_secret")
PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "bot.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS environment variable is required")
if not WEBHOOK_BASE:
    raise RuntimeError("WEBHOOK_BASE environment variable is required (e.g. https://your-service.onrender.com)")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lwox-bot")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = FastAPI(title="LWOX Gold Bot")

# ---------- Database ----------
def db():
    return sqlite3.connect(DB_PATH, timeout=30)

def init_db():
    with closing(db()) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER NOT NULL DEFAULT 0,
            muted_until TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gold INTEGER NOT NULL,
            price INTEGER NOT NULL,
            screenshot_file_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        """)
        con.commit()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def ensure_user(user):
    with closing(db()) as con:
        con.execute(
            "INSERT INTO users(user_id, username, first_name, created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (user.id, user.username or "", user.first_name or "", now_iso())
        )
        con.commit()

def get_user(user_id):
    with closing(db()) as con:
        return con.execute("SELECT user_id, username, first_name, balance, muted_until FROM users WHERE user_id=?", (user_id,)).fetchone()

def set_balance(user_id, amount):
    with closing(db()) as con:
        con.execute("UPDATE users SET balance=? WHERE user_id=?", (amount, user_id))
        con.commit()

def change_balance(user_id, delta):
    with closing(db()) as con:
        cur = con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (delta, user_id))
        con.commit()
        return cur.rowcount

def set_mute(user_id, until):
    with closing(db()) as con:
        con.execute("UPDATE users SET muted_until=? WHERE user_id=?", (until, user_id))
        con.commit()

def create_order(user_id, gold, price, file_id):
    with closing(db()) as con:
        cur = con.execute(
            "INSERT INTO orders(user_id,gold,price,screenshot_file_id,created_at) VALUES(?,?,?,?,?)",
            (user_id, gold, price, file_id, now_iso())
        )
        con.commit()
        return cur.lastrowid

def update_order(order_id, status):
    with closing(db()) as con:
        con.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        con.commit()

def get_order(order_id):
    with closing(db()) as con:
        return con.execute("SELECT id,user_id,gold,price,status,created_at FROM orders WHERE id=?", (order_id,)).fetchone()

def all_user_ids():
    with closing(db()) as con:
        return [r[0] for r in con.execute("SELECT user_id FROM users").fetchall()]

# ---------- Keyboards ----------
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🪙 GOLD OLISH"), KeyboardButton(text="🧮 GOLD HISOBLASH")],
        [KeyboardButton(text="💰 BALANCE"), KeyboardButton(text="📞 SUPPORT")],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📢 XABAR YUBORISH")],
        [KeyboardButton(text="➕ HISOB TO‘LDIRISH"), KeyboardButton(text="➖ HISOB AYRISH")],
        [KeyboardButton(text="🔇 MUTE BERISH")],
    ], resize_keyboard=True)

def order_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"order:done:{order_id}"),
        InlineKeyboardButton(text="❌ Bajarilmadi", callback_data=f"order:fail:{order_id}")
    ]])

# ---------- User state ----------
states = {}

def is_admin(uid): return uid in ADMIN_IDS

def is_muted(uid):
    row = get_user(uid)
    if not row or not row[4]: return False
    try:
        until = datetime.fromisoformat(row[4])
        if datetime.now(timezone.utc) < until:
            return True
        set_mute(uid, None)
    except Exception:
        return False
    return False

@dp.message(CommandStart())
async def start(message: Message):
    ensure_user(message.from_user)
    states.pop(message.from_user.id, None)
    if is_admin(message.from_user.id):
        await message.answer("👑 <b>LWOX GOLD — Admin panel</b>", reply_markup=admin_kb())
    else:
        await message.answer(
            "👋 Assalomu alaykum!\n\n🪙 <b>LWOX GOLD</b> botiga xush kelibsiz.\nKerakli bo‘limni tanlang:",
            reply_markup=main_kb()
        )

@dp.message(F.text == "🪙 GOLD OLISH")
async def gold_buy(message: Message):
    if is_muted(message.from_user.id): return await message.answer("🔇 Siz vaqtincha mute qilingansiz.")
    states[message.from_user.id] = "gold_amount"
    await message.answer(f"🪙 Qancha Gold olmoqchisiz?\n\nKurs: <b>1 Gold = {GOLD_RATE} so‘m</b>\n\nMasalan: <code>100</code>")

@dp.message(F.text == "🧮 GOLD HISOBLASH")
async def calc_start(message: Message):
    if is_muted(message.from_user.id): return await message.answer("🔇 Siz vaqtincha mute qilingansiz.")
    states[message.from_user.id] = "calc"
    await message.answer(f"🧮 Gold miqdorini yozing.\nKurs: 1 Gold = {GOLD_RATE} so‘m")

@dp.message(F.text == "💰 BALANCE")
async def balance(message: Message):
    if is_muted(message.from_user.id): return await message.answer("🔇 Siz vaqtincha mute qilingansiz.")
    row = get_user(message.from_user.id)
    await message.answer(f"💰 Balansingiz: <b>{row[3]:,} so‘m</b>".replace(",", " ") + f"\n\nHisob to‘ldirish: @{PAYMENT_USERNAME}")

@dp.message(F.text == "📞 SUPPORT")
async def support(message: Message):
    await message.answer(f"📞 Qo‘llab-quvvatlash: @{PAYMENT_USERNAME}")

@dp.message(F.photo)
async def photo_handler(message: Message):
    uid = message.from_user.id
    if is_muted(uid): return await message.answer("🔇 Siz vaqtincha mute qilingansiz.")
    state = states.get(uid)
    if state != "await_screenshot":
        return
    data = states.pop(uid)
    order_id = create_order(uid, data["gold"], data["price"], message.photo[-1].file_id)
    username = f"@{message.from_user.username}" if message.from_user.username else "username yo‘q"
    caption = (
        f"🆕 <b>Yangi GOLD buyurtma #{order_id}</b>\n\n"
        f"👤 Mijoz: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"🔗 {username}\n"
        f"🪙 Gold: <b>{data['gold']}</b>\n"
        f"💵 Summa: <b>{data['price']:,} so‘m</b>\n\n"
        f"📸 To‘lov skrinshoti yuborildi."
    ).replace(",", " ")
    for aid in ADMIN_IDS:
        try:
            await bot.send_photo(aid, message.photo[-1].file_id, caption=caption, reply_markup=order_kb(order_id))
        except Exception as e: log.warning("admin notify %s: %s", aid, e)
    await message.answer(f"✅ Buyurtmangiz qabul qilindi!\n\nBuyurtma: <b>#{order_id}</b>\n🪙 Gold: {data['gold']}\n💵 {data['price']:,} so‘m\n\nAdmin tekshirishi kutilmoqda.".replace(",", " "), reply_markup=main_kb())

@dp.message()
async def text_handler(message: Message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    text = (message.text or "").strip()

    if is_admin(uid):
        await admin_text(message, text)
        return
    if is_muted(uid):
        return await message.answer("🔇 Siz vaqtincha mute qilingansiz.")

    state = states.get(uid)
    if state == "gold_amount":
        try:
            gold = int(text.replace(" ", ""))
            if gold <= 0 or gold > 10000000: raise ValueError
        except ValueError:
            return await message.answer("❌ Faqat musbat son kiriting. Masalan: 100")
        price = gold * GOLD_RATE
        states[uid] = {"step":"confirm","gold":gold,"price":price}
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Skrinshot yuboraman", callback_data="buy:shot")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="buy:cancel")]
        ])
        await message.answer(f"🪙 Gold: <b>{gold}</b>\n💵 Narx: <b>{price:,} so‘m</b>\n\nTo‘lovni @{PAYMENT_USERNAME} orqali amalga oshirib, skrinshot yuboring.".replace(",", " "), reply_markup=kb)
        return
    if state == "calc":
        try:
            gold = int(text.replace(" ", "")); assert gold > 0
        except Exception:
            return await message.answer("❌ Masalan: 500")
        await message.answer(f"🧮 <b>{gold} Gold = {gold * GOLD_RATE:,} so‘m</b>".replace(",", " "))
        states.pop(uid, None)
        return
    await message.answer("Menyudan kerakli bo‘limni tanlang.", reply_markup=main_kb())

async def admin_text(message: Message, text: str):
    uid = message.from_user.id
    state = states.get(uid)
    if text == "📢 XABAR YUBORISH":
        states[uid] = "broadcast"; return await message.answer("📢 Yuboriladigan xabarni yuboring. U barcha mijozlarga jo‘natiladi.")
    if text == "➕ HISOB TO‘LDIRISH":
        states[uid] = "add_balance_id"; return await message.answer("🆔 Mijoz Telegram ID sini yuboring.")
    if text == "➖ HISOB AYRISH":
        states[uid] = "sub_balance_id"; return await message.answer("🆔 Mijoz Telegram ID sini yuboring.")
    if text == "🔇 MUTE BERISH":
        states[uid] = "mute_id"; return await message.answer("🆔 Mijoz Telegram ID sini yuboring.")

    if state == "broadcast":
        states.pop(uid, None); ok=0
        for cid in all_user_ids():
            try: await bot.copy_message(cid, message.chat.id, message.message_id); ok += 1
            except Exception: pass
        return await message.answer(f"✅ Xabar {ok} ta mijozga yuborildi.")
    if state in ("add_balance_id", "sub_balance_id"):
        try: cid=int(text); assert get_user(cid)
        except Exception: return await message.answer("❌ Bunday mijoz topilmadi. Telegram ID ni tekshiring.")
        states[uid] = ("add_balance_amount" if state=="add_balance_id" else "sub_balance_amount", cid)
        return await message.answer("💰 Summani so‘mda yuboring. Masalan: 50000")
    if isinstance(state, tuple) and state[0] in ("add_balance_amount","sub_balance_amount"):
        try: amount=int(text.replace(" ","")); assert amount > 0
        except Exception: return await message.answer("❌ Musbat summa kiriting.")
        cid=state[1]; delta=amount if state[0]=="add_balance_amount" else -amount
        row=get_user(cid); newbal=row[3]+delta
        if newbal < 0: return await message.answer("❌ Balans manfiy bo‘lib qoladi.")
        change_balance(cid, delta); states.pop(uid,None)
        sign="+" if delta>0 else "-"
        try: await bot.send_message(cid, f"💰 Balansingiz {sign}<b>{amount:,} so‘m</b> o‘zgartirildi.\nYangi balans: <b>{newbal:,} so‘m</b>".replace(","," "))
        except Exception: pass
        return await message.answer(f"✅ Mijoz <code>{cid}</code> balansi yangilandi: <b>{newbal:,} so‘m</b>".replace(","," "))
    if state == "mute_id":
        try: cid=int(text); assert get_user(cid)
        except Exception: return await message.answer("❌ Mijoz topilmadi.")
        states[uid] = ("mute_minutes", cid)
        return await message.answer("⏱ Necha daqiqaga mute? Masalan: 60")
    if isinstance(state, tuple) and state[0] == "mute_minutes":
        try: mins=int(text); assert mins > 0
        except Exception: return await message.answer("❌ Musbat daqiqa kiriting.")
        cid=state[1]; until=datetime.now(timezone.utc)+timedelta(minutes=mins); set_mute(cid, until.isoformat()); states.pop(uid,None)
        try: await bot.send_message(cid, f"🔇 Siz <b>{mins} daqiqaga</b> mute qilindingiz.")
        except Exception: pass
        return await message.answer(f"✅ <code>{cid}</code> {mins} daqiqaga mute qilindi.")

@dp.callback_query(F.data == "buy:shot")
async def buy_shot(call: CallbackQuery):
    uid=call.from_user.id; state=states.get(uid)
    if not isinstance(state,dict): return await call.answer("Buyurtma topilmadi", show_alert=True)
    states[uid] = {"gold":state["gold"],"price":state["price"],"step":"await_screenshot"}
    await call.message.answer("📸 Endi to‘lov skrinshotini shu yerga yuboring.")
    await call.answer()

@dp.callback_query(F.data == "buy:cancel")
async def buy_cancel(call: CallbackQuery):
    states.pop(call.from_user.id,None); await call.message.answer("❌ Buyurtma bekor qilindi.", reply_markup=main_kb()); await call.answer()

@dp.callback_query(F.data.startswith("order:"))
async def order_action(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Ruxsat yo‘q", show_alert=True)
    _, action, oid_s = call.data.split(":"); oid=int(oid_s); order=get_order(oid)
    if not order: return await call.answer("Buyurtma topilmadi", show_alert=True)
    if order[4] != "pending": return await call.answer("Bu buyurtma allaqachon yopilgan", show_alert=True)
    status="done" if action=="done" else "failed"; update_order(oid,status)
    uid,gold,price=order[1],order[2],order[3]
    try:
        if status=="done":
            await bot.send_message(uid, f"✅ <b>Buyurtma #{oid} bajarildi!</b>\n🪙 Gold: {gold}")
            await call.message.edit_reply_markup(reply_markup=None)
        else:
            await bot.send_message(uid, f"❌ <b>Buyurtma #{oid} bajarilmadi.</b>\nAloqa: @{PAYMENT_USERNAME}")
            await call.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    await call.answer("Bajarildi" if status=="done" else "Bajarilmadi")

@app.get("/")
async def health():
    return {"status":"ok","service":"LWOX Gold Bot"}

@app.post("/webhook")
async def webhook(request: Request):
    secret=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
    if secret != WEBHOOK_SECRET:
        return {"ok":False}
    data=await request.json()
    from aiogram.types import Update
    update=Update.model_validate(data, context={"bot":bot})
    await dp.feed_update(bot, update)
    return {"ok":True}

@app.on_event("startup")
async def startup():
    init_db()
    url=f"{WEBHOOK_BASE}/webhook"
    await bot.set_webhook(url=url, secret_token=WEBHOOK_SECRET, drop_pending_updates=True)
    log.info("Webhook set: %s", url)

@app.on_event("shutdown")
async def shutdown():
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()

# Render runs uvicorn via start command.

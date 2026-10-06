import os, sqlite3, math
from contextlib import closing
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN=os.getenv("BOT_TOKEN","").strip()
BASE=os.getenv("WEBHOOK_BASE","").strip().rstrip("/")
ADMINS={int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
if not TOKEN: raise RuntimeError("BOT_TOKEN is missing")
if not BASE: raise RuntimeError("WEBHOOK_BASE is missing")

DB="zex_shop.db"; RATE=120; WEBHOOK=BASE+"/webhook"
bot=Bot(TOKEN); dp=Dispatcher(); app=FastAPI(); state={}; broadcast=set()

def con(): return sqlite3.connect(DB)
def init():
    with closing(con()) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,username TEXT DEFAULT '',first_name TEXT DEFAULT '',
        balance REAL DEFAULT 0,muted_until TEXT DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,username TEXT,gold INTEGER,
        cost REAL,pattern TEXT,admin_gold INTEGER,photo_file_id TEXT,status TEXT DEFAULT 'PENDING',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS drafts(
        user_id INTEGER PRIMARY KEY,step TEXT,gold INTEGER DEFAULT 0,cost REAL DEFAULT 0,
        pattern TEXT DEFAULT '')""")
        c.commit()
def save(u):
    with closing(con()) as c:
        c.execute("INSERT OR IGNORE INTO users(user_id,username,first_name) VALUES(?,?,?)",(u.id,u.username or "",u.first_name or ""))
        c.execute("UPDATE users SET username=?,first_name=? WHERE user_id=?",(u.username or "",u.first_name or "",u.id)); c.commit()
def bal(uid):
    with closing(con()) as c:
        r=c.execute("SELECT balance FROM users WHERE user_id=?",(uid,)).fetchone()
    return float(r[0]) if r else 0
def change(uid,x):
    with closing(con()) as c: c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(x,uid)); c.commit()
def admin(uid): return uid in ADMINS
def muted(uid):
    with closing(con()) as c: r=c.execute("SELECT muted_until FROM users WHERE user_id=?",(uid,)).fetchone()
    try: return bool(r and r[0] and datetime.fromisoformat(r[0])>datetime.utcnow())
    except: return False

def set_draft(uid, step, gold=0, cost=0, pattern=""):
    with closing(con()) as c:
        c.execute("INSERT OR REPLACE INTO drafts(user_id,step,gold,cost,pattern) VALUES(?,?,?,?,?)",
                  (uid,step,gold,cost,pattern)); c.commit()

def get_draft(uid):
    with closing(con()) as c:
        r=c.execute("SELECT step,gold,cost,pattern FROM drafts WHERE user_id=?",(uid,)).fetchone()
    if not r: return None
    return {"step":r[0],"gold":int(r[1]),"cost":float(r[2]),"pattern":r[3] or ""}

def clear_draft(uid):
    with closing(con()) as c:
        c.execute("DELETE FROM drafts WHERE user_id=?",(uid,)); c.commit()

def main():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎟 PROMOKOD"),KeyboardButton(text="👤 PROFIL")],
        [KeyboardButton(text="🧮 GOLD HISOBLASH"),KeyboardButton(text="🛒 GOLD SOTIB OLISH")],
        [KeyboardButton(text="💳 PUL KIRITISH")]],resize_keyboard=True)
def admink():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 STATISTIKA"),KeyboardButton(text="📢 XABAR YUBORISH")],
        [KeyboardButton(text="💰 BALANS QO‘SHISH"),KeyboardButton(text="➖ BALANS AYIRISH")],
        [KeyboardButton(text="🔇 MUTE"),KeyboardButton(text="⬅️ ADMIN PANELDAN CHIQISH")]],resize_keyboard=True)
def obtn(i):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ HA",callback_data=f"yes:{i}"),
        InlineKeyboardButton(text="❌ YO‘Q",callback_data=f"no:{i}")]])

@dp.message(CommandStart())
async def start(m):
    save(m.from_user); state.pop(m.from_user.id,None); clear_draft(m.from_user.id)
    await m.answer("👋 ZEX SHOP ga xush kelibsiz!\n\n🪙 1 Gold = 120 so‘m\nKerakli bo‘limni tanlang 👇",reply_markup=main())

@dp.message(Command("admin", "Admin", "ADMIN"))
async def admin_cmd(m):
    if not admin(m.from_user.id):
        await m.answer(
            f"⛔ Sizda admin huquqi yo‘q.\n\n"
            f"🆔 Sizning Telegram ID: {m.from_user.id}\n\n"
            "Render → Environment Variables → ADMIN_IDS ga shu ID ni yozing, "
            "keyin Deploy qiling."
        )
        return
    state.pop(m.from_user.id,None)
    broadcast.discard(m.from_user.id)
    await m.answer("🛠 ADMIN PANEL",reply_markup=admink())

@dp.message(lambda m: m.photo is not None)
async def photo(m):
    uid=m.from_user.id
    save(m.from_user)
    s=get_draft(uid)
    if not isinstance(s,dict) or s.get("step")!="photo":
        await m.answer("❌ Hozir rasm qabul qilish bosqichida emassiz. 🛒 GOLD SOTIB OLISH bo‘limidan qaytadan boshlang.")
        return

    ag=math.ceil(s["gold"]*1.2)
    pid=m.photo[-1].file_id
    with closing(con()) as c:
        cur=c.execute(
            "INSERT INTO orders(user_id,username,gold,cost,pattern,admin_gold,photo_file_id) VALUES(?,?,?,?,?,?,?)",
            (uid,m.from_user.username or "",s["gold"],s["cost"],s["pattern"],ag,pid))
        oid=cur.lastrowid; c.commit()
    clear_draft(uid)

    await m.answer(
        f"✅ BUYURTMA QABUL QILINDI!\n\n"
        f"🪙 Gold: {s['gold']}\n💰 Narxi: {s['cost']:,.0f} so‘m\n"
        f"🔢 Pattern: {s['pattern']}\n\nAdmin buyurtmani tekshiradi.",
        reply_markup=main())

    cap=(f"🛒 YANGI BUYURTMA #{oid}\n\n👤 MIJOZ: {uid}\n"
         f"💰 NARXI: {s['cost']:,.0f} so‘m\n🔢 PATTERN: {s['pattern']}\n"
         f"🪙 GOLD: {ag} (20% qo‘shilgan)\n\nBUYURTMA AMALGA OSHDIMI?")
    for a in ADMINS:
        try: await bot.send_photo(a,pid,caption=cap,reply_markup=obtn(oid))
        except Exception as e: print("ADMIN SEND ERROR",e,flush=True)

@dp.callback_query(lambda c:c.data.startswith("yes:") or c.data.startswith("no:"))
async def order_cb(q):
    if not admin(q.from_user.id): return await q.answer("⛔ Admin uchun.",show_alert=True)
    ok=q.data.startswith("yes:"); oid=int(q.data.split(":")[1])
    with closing(con()) as c:
        r=c.execute("SELECT user_id,cost,status FROM orders WHERE id=?",(oid,)).fetchone()
        if not r: return await q.answer("Buyurtma topilmadi.",show_alert=True)
        uid,cost,status=r
        if status!="PENDING": return await q.answer("Allaqachon ko‘rib chiqilgan.",show_alert=True)
        c.execute("UPDATE orders SET status=? WHERE id=?",("DONE" if ok else "CANCELED",oid)); c.commit()
    if not ok: change(uid,cost)
    await q.message.edit_reply_markup(reply_markup=None); await q.answer("Saqlandi.")
    try:
        await bot.send_message(uid,("✅ BUYURTMANGIZ BAJARILDI!" if ok else f"❌ BUYURTMA BEKOR QILINDI.\n💰 {cost:,.0f} so‘m balansingizga qaytarildi."))
    except: pass

@dp.message()
async def msg(m):
    uid=m.from_user.id; save(m.from_user)
    if muted(uid) and not admin(uid): return await m.answer("🔇 Siz vaqtincha bloklangansiz.")
    t=m.text or ""; s=state.get(uid)

    # Telegram may deliver /Admin as plain text because bot commands are normally lowercase.
    if t.strip().lower() == "/admin":
        if not admin(uid):
            return await m.answer(
                f"⛔ Sizda admin huquqi yo‘q.\n\n"
                f"🆔 Sizning Telegram ID: {uid}\n\n"
                "Render → Environment Variables → ADMIN_IDS ga shu ID ni yozing, keyin Deploy qiling."
            )
        state.pop(uid,None); broadcast.discard(uid)
        return await m.answer("🛠 ADMIN PANEL",reply_markup=admink())

    if s=="calc":
        try:
            g=int(t.replace(" ","")); assert g>0
            await m.answer(f"🧮 {g:,} Gold × 120 so‘m = {g*RATE:,} so‘m")
        except: await m.answer("❌ Masalan: 100")
        state.pop(uid,None); return

    draft=get_draft(uid)

    if s=="buy":
        try: g=int(t.replace(" ","")); assert g>0
        except: return await m.answer("❌ Gold miqdorini son bilan kiriting. Masalan: 100")
        cost=g*RATE
        if bal(uid)<cost:
            state.pop(uid,None); clear_draft(uid)
            return await m.answer(f"❌ Balans yetarli emas.\nKerak: {cost:,} so‘m\nBalans: {bal(uid):,.0f} so‘m",reply_markup=main())
        change(uid,-cost); set_draft(uid,"pattern",g,cost,""); state.pop(uid,None)
        market_gold=math.ceil(g*1.2)
        await m.answer_photo(
            types.FSInputFile("g22_flock.jpg"),
            caption=(
                "BOZORDAN G22 FLOCK SOTIB OLING\n"
                f"VA UNI QAYTA ORDERGA SHU {market_gold} NARXGA BOZORGA QO‘YING\n\n"
                "BOT AYTGAN BUYRUQLARNI TO‘G‘RI BAJARING.\n"
                "FIKRINGIZ O‘ZGARSA BEKOR QILING."
            )
        )
        await m.answer_photo(types.FSInputFile("g22_glock_extra.jpg"))
        return await m.answer("1️⃣ Pattern sonini yuboring. Masalan: 756")

    if draft and draft.get("step")=="pattern":
        pattern=t.strip()
        if not pattern: return await m.answer("❌ Pattern sonini yuboring. Masalan: 756")
        set_draft(uid,"photo",draft["gold"],draft["cost"],pattern)
        return await m.answer("2️⃣ Endi STANDOFF 2 profilingizning rasmini yuboring 📸")

    if isinstance(s,dict) and s.get("step") in ("add","sub","mute"):
        try:
            a,b=t.split(); a=int(a); b=float(b)
            if s["step"]=="mute":
                until=datetime.utcnow()+timedelta(minutes=int(b))
                with closing(con()) as c: c.execute("UPDATE users SET muted_until=? WHERE user_id=?",(until.isoformat(),a)); c.commit()
                out=f"🔇 {a} {int(b)} daqiqaga mute qilindi."
            else:
                change(a,b if s["step"]=="add" else -b); out=f"✅ {a} hisobiga o‘zgarish kiritildi."
        except: out="Format: USER_ID SUMMA\nMasalan: 123456789 50000"
        state.pop(uid,None); return await m.answer(out,reply_markup=admink())

    if uid in broadcast and admin(uid):
        sent=0
        with closing(con()) as c: users=c.execute("SELECT user_id FROM users").fetchall()
        for (x,) in users:
            try: await bot.send_message(x,t); sent+=1
            except: pass
        broadcast.remove(uid); return await m.answer(f"📢 {sent} ta foydalanuvchiga yuborildi.",reply_markup=admink())

    if admin(uid):
        if t=="📊 STATISTIKA":
            with closing(con()) as c:
                u=c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                o=c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                p=c.execute("SELECT COUNT(*) FROM orders WHERE status='PENDING'").fetchone()[0]
                d=c.execute("SELECT COUNT(*) FROM orders WHERE status='DONE'").fetchone()[0]
                x=c.execute("SELECT COUNT(*) FROM orders WHERE status='CANCELED'").fetchone()[0]
                g=c.execute("SELECT COALESCE(SUM(gold),0) FROM orders WHERE status='DONE'").fetchone()[0]
            return await m.answer(f"📊 STATISTIKA\n\n👥 Foydalanuvchilar: {u}\n🛒 Buyurtmalar: {o}\n⏳ Kutilmoqda: {p}\n✅ Bajarilgan: {d}\n❌ Bekor: {x}\n🪙 Bajarilgan Gold: {g}")
        if t=="📢 XABAR YUBORISH":
            broadcast.add(uid); return await m.answer("📢 Endi xabarni yozing.")
        if t=="💰 BALANS QO‘SHISH":
            state[uid]={"step":"add"}; return await m.answer("USER_ID SUMMA\nMasalan: 123456789 50000")
        if t=="➖ BALANS AYIRISH":
            state[uid]={"step":"sub"}; return await m.answer("USER_ID SUMMA\nMasalan: 123456789 50000")
        if t=="🔇 MUTE":
            state[uid]={"step":"mute"}; return await m.answer("USER_ID DAQIQA\nMasalan: 123456789 60")
        if t=="⬅️ ADMIN PANELDAN CHIQISH": return await m.answer("Asosiy menyu.",reply_markup=main())

    if t=="👤 PROFIL": return await m.answer(f"👤 PROFIL\n\n🆔 ID: {uid}\n💰 Balans: {bal(uid):,.0f} so‘m")
    if t=="💳 PUL KIRITISH": return await m.answer("💳 Pul kiritish uchun: @lwox_org")
    if t=="🎟 PROMOKOD": return await m.answer("🎟 Promokod bo‘limi.")
    if t=="🧮 GOLD HISOBLASH": state[uid]="calc"; return await m.answer("🧮 GOLD MIQDORINI KIRITING\n\nKurs: 1 Gold = 120 so‘m\nMasalan: 100")
    if t=="🛒 GOLD SOTIB OLISH": state[uid]="buy"; return await m.answer("🪙 GOLD MIQDORINI KIRITING\n\nKurs: 1 Gold = 120 so‘m\nMasalan: 100")
    await m.answer("Menyudan kerakli bo‘limni tanlang 👇",reply_markup=main())

@app.get("/")
async def root(): return {"status":"ZEX SHOP is running","webhook":WEBHOOK}
@app.get("/health")
async def health(): return {"ok":True}
@app.post("/webhook")
async def webhook(r:Request):
    try:
        u=types.Update.model_validate(await r.json()); await dp.feed_update(bot,u); return {"ok":True}
    except Exception as e:
        print("WEBHOOK ERROR",repr(e),flush=True); return {"ok":False}
@app.on_event("startup")
async def startup():
    init()
    try:
        me=await bot.get_me(); print(f"BOT CONNECTED @{me.username}",flush=True)
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.set_webhook(WEBHOOK,allowed_updates=dp.resolve_used_update_types(),drop_pending_updates=False)
        w=await bot.get_webhook_info(); print(f"WEBHOOK SET {w.url} pending={w.pending_update_count}",flush=True)
    except Exception as e: print("STARTUP ERROR",repr(e),flush=True)
@app.on_event("shutdown")
async def shutdown(): await bot.session.close()

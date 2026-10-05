# LWOX GOLD Telegram Bot

Render Web Service uchun tayyorlangan Telegram bot.

## Mijoz menyusi
- 🪙 GOLD OLISH — Gold miqdorini kiritadi, narx hisoblanadi, to‘lov skrinshoti yuboriladi. Adminlarga buyurtma tugmalari bilan keladi.
- 🧮 GOLD HISOBLASH — Gold narxini hisoblaydi.
- 💰 BALANCE — mijoz balansini ko‘rsatadi.
- 📞 SUPPORT — @lwox_org.

## Admin paneli
Faqat `ADMIN_IDS` dagi Telegram IDlar ko‘radi:
- 📢 XABAR YUBORISH — barcha mijozlarga xabar yuborish.
- ➕ HISOB TO‘LDIRISH — mijoz ID orqali balans qo‘shish.
- ➖ HISOB AYRISH — mijoz ID orqali balans ayirish.
- 🔇 MUTE BERISH — mijoz ID va daqiqalar orqali vaqtli mute.

## Render sozlamalari
Environment variables:
- `BOT_TOKEN` — @BotFather token
- `ADMIN_IDS` — admin Telegram ID, bir nechta bo‘lsa vergul bilan
- `WEBHOOK_BASE` — Render service URL, masalan `https://lwox-gold-bot.onrender.com`
- `WEBHOOK_SECRET` — istalgan maxfiy uzun qiymat; render.yaml avtomatik generatsiya qiladi
- `PAYMENT_USERNAME` — `lwox_org`
- `GOLD_RATE` — 1 Gold narxi, default 105 so‘m

Deploydan keyin bot webhookni o‘zi o‘rnatadi.

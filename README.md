ZEX SHOP - GOLD MESSAGE + GLOCK IMAGE FIX

After the customer enters Gold quantity, the existing G22 Flock image is kept, and an additional Glock image is sent.
The message shows the customer's Gold quantity with +20% for the market price.
Example: 100 Gold -> 120 market price.

Render Start:
uvicorn bot:app --host 0.0.0.0 --port $PORT

ENV:
BOT_TOKEN=BotFather token
ADMIN_IDS=Telegram numeric ID
WEBHOOK_BASE=https://zex-shop.onrender.com

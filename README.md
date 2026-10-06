ZEX SHOP PHOTO FIXED
The profile screenshot step is persisted in SQLite, so it survives Render restarts.
Render Start: uvicorn bot:app --host 0.0.0.0 --port $PORT
ENV: BOT_TOKEN, ADMIN_IDS, WEBHOOK_BASE=https://zex-shop.onrender.com

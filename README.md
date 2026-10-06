ZEX SHOP - FIXED WEBHOOK VERSION

Python: 3.11.9

Render Build Command:
pip install --only-binary=:all: -r requirements.txt

Render Start Command:
uvicorn bot:app --host 0.0.0.0 --port $PORT

Environment:
BOT_TOKEN = BotFather token
ADMIN_IDS = Telegram ID (optional)
WEBHOOK_BASE = https://zex-shop.onrender.com

IMPORTANT:
1. Upload this project / replace the old files.
2. Set the three environment variables.
3. Deploy.
4. Open https://zex-shop.onrender.com/ and make sure it says ZEX SHOP is running.
5. BotFather token must belong to the exact bot you are opening in Telegram.
6. After startup logs show BOT CONNECTED and WEBHOOK SET, send /start.

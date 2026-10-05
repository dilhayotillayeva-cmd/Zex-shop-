ZEX SHOP Telegram Bot

Python: 3.11.9

Render:
Build Command:
pip install --only-binary=:all: -r requirements.txt

Start Command:
uvicorn bot:app --host 0.0.0.0 --port $PORT

Environment Variables:
BOT_TOKEN=BotFather token
ADMIN_IDS=Telegram admin ID (optional for this basic version)
WEBHOOK_BASE=https://YOUR-SERVICE-NAME.onrender.com

After deploy, open the bot and press /start.

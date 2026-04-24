import os
import threading
import time
from flask import Flask
from bridge import telegram_polling_loop, bale_polling_loop

app = Flask(__name__)

@app.route("/")
def home():
    return "Telegram ↔ Bale Bridge Bot is Running ✓"


if __name__ == "__main__":
    # Start Telegram polling
    threading.Thread(target=telegram_polling_loop, daemon=True).start()

    # Start Bale polling
    threading.Thread(target=bale_polling_loop, daemon=True).start()

    # Web server for Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

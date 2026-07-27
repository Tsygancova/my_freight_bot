import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data.db")

# Платформы (пока только тестовая)
PLATFORMS = [
    {
        "name": "mock",
        "enabled": True,
        "credentials": {}
    }
]

# Интервал проверки заказов (секунды)
POLL_INTERVAL = 60
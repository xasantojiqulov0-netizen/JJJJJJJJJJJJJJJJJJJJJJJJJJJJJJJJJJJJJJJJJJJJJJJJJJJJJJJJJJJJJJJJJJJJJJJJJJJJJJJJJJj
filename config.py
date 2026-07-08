import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

# Railway PostgreSQL yoki lokal SQLite
_raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///stalker.db")
if _raw_db_url.startswith("postgres://"):
    _raw_db_url = _raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw_db_url.startswith("postgresql://") and "+asyncpg" not in _raw_db_url:
    _raw_db_url = _raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
DATABASE_URL: str = _raw_db_url

CARD_NUMBER: str = os.getenv("CARD_NUMBER", "0000 0000 0000 0000")
CARD_OWNER: str = os.getenv("CARD_OWNER", "Admin")

# Default tariflar — faqat DB bo'sh bo'lganda bir marta seed qilinadi.
# Keyinchalik admin paneldan boshqariladi.
DEFAULT_TARIFFS: list[dict] = [
    {"label": "1 oylik",  "months": 1,  "price": int(os.getenv("PRICE_1_MONTH",  "30000"))},
    {"label": "3 oylik",  "months": 3,  "price": int(os.getenv("PRICE_3_MONTH",  "80000"))},
    {"label": "6 oylik",  "months": 6,  "price": int(os.getenv("PRICE_6_MONTH",  "150000"))},
    {"label": "9 oylik",  "months": 9,  "price": int(os.getenv("PRICE_9_MONTH",  "210000"))},
    {"label": "1 yillik", "months": 12, "price": int(os.getenv("PRICE_12_MONTH", "270000"))},
]

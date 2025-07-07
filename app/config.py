import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SQL_DIR = BASE_DIR.parent / "sql"
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

APP_NAME = "Counterweight"
APP_VERSION = "3.0.0"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://counterweight:counterweight@localhost:5432/counterweight",
)
DB_CONNECT_RETRIES = int(os.getenv("DB_CONNECT_RETRIES", "20"))
DB_CONNECT_DELAY_SECONDS = float(os.getenv("DB_CONNECT_DELAY_SECONDS", "1.5"))
AUTO_INIT_DB = os.getenv("AUTO_INIT_DB", "1") == "1"
SEED_SOURCE_BANK = os.getenv("SEED_SOURCE_BANK", "1") == "1"
TESTING = os.getenv("TESTING", "0") == "1"
MAX_CLAIMS_PER_ARTICLE = int(os.getenv("MAX_CLAIMS_PER_ARTICLE", "8"))
TOP_EVIDENCE_PER_CLAIM = int(os.getenv("TOP_EVIDENCE_PER_CLAIM", "4"))
DEFAULT_ARTICLE_LIMIT = int(os.getenv("DEFAULT_ARTICLE_LIMIT", "25"))

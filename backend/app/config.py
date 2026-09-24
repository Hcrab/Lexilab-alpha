import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv


load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now():
    """Return the current time in Beijing."""
    return datetime.now(BEIJING_TZ)


class Config:
    """Configuration for the archived quiz platform."""

    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "lexilab_alpha")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    CORS_ORIGINS = [
        os.getenv("FRONT_ORIGIN", "http://localhost:3000"),
        "http://127.0.0.1:3000",
    ]

"""Create a small, fictional quiz dataset in an isolated local MongoDB."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

uri = os.getenv("MONGO_URI", "")
database_name = os.getenv("MONGO_DB_NAME", "")
password = os.getenv("DEMO_PASSWORD", "")
parsed = urlparse(uri)

if parsed.scheme != "mongodb" or parsed.hostname not in {"127.0.0.1", "localhost"}:
    raise SystemExit("Demo seeding requires a loopback MongoDB URI")
if database_name != "lexilab_alpha_demo":
    raise SystemExit("Demo seeding requires MONGO_DB_NAME=lexilab_alpha_demo")
if len(password) < 12:
    raise SystemExit("Set DEMO_PASSWORD to a local password of at least 12 characters")

client = MongoClient(uri, serverSelectionTimeoutMS=3000)
client.admin.command("ping")
db = client[database_name]
now = datetime.now(timezone.utc)

for username, role, english_name in (
    ("demo_learner", "user", "Avery"),
    ("demo_teacher", "admin", "Morgan"),
):
    db.users.update_one(
        {"username": username},
        {"$set": {
            "role": role,
            "english_name": english_name,
            "password_hash": generate_password_hash(password),
        }},
        upsert=True,
    )

today_id = ObjectId("690000000000000000000001")
past_id = ObjectId("690000000000000000000002")
today_items = [
    {
        "id": "demo-today-1",
        "type": "fill-in-the-blank",
        "word": "resilient",
        "definition": "Able to recover after difficulty.",
        "prompt": "The young tree remained ___ after the storm.",
        "answer": "resilient",
    },
    {
        "id": "demo-today-2",
        "type": "sentence",
        "word": "curious",
        "definition": "Eager to learn or discover something.",
    },
]
past_items = [
    {
        "id": "demo-past-1",
        "type": "fill-in-the-blank",
        "word": "thoughtful",
        "definition": "Showing care for other people's needs.",
        "prompt": "Her ___ note made the new student feel welcome.",
        "answer": "thoughtful",
    },
    {
        "id": "demo-past-2",
        "type": "sentence",
        "word": "patient",
        "definition": "Able to stay calm while waiting.",
    },
]

for quiz_id, name, created_at, items in (
    (today_id, "Everyday English · A fresh start", now, today_items),
    (past_id, "Words in context · Practice set", now - timedelta(days=2), past_items),
):
    db.quizzes.update_one(
        {"_id": quiz_id},
        {"$set": {
            "name": name,
            "type": "weekday",
            "status": "published",
            "created_at": created_at,
            "publish_at": None,
            "data": {"items": items},
        }},
        upsert=True,
    )

db.results.update_one(
    {"_id": ObjectId("690000000000000000000003")},
    {"$set": {
        "username": "demo_learner",
        "quiz_id": past_id,
        "correct": 6,
        "total": 6,
        "passed": True,
        "time_spent": 82,
        "ts": now - timedelta(days=2),
        "details": {
            "name": "Words in context · Practice set",
            "questions": [
                {
                    "id": "demo-past-1",
                    "type": "fill-in-the-blank",
                    "word": "thoughtful",
                    "definition": past_items[0]["definition"],
                    "prompt": past_items[0]["prompt"],
                    "answer": "thoughtful",
                    "correct": True,
                    "correctAnswer": "thoughtful",
                    "feedback": "Correct use of the word.",
                },
                {
                    "id": "demo-past-2",
                    "type": "sentence",
                    "word": "patient",
                    "definition": past_items[1]["definition"],
                    "answer": "The patient tutor explained it again.",
                    "score": 4,
                    "feedback": "Clear and natural sentence.",
                },
            ],
        },
    }},
    upsert=True,
)

print("Seeded two fictional users, two quizzes, and one practice result.")

"""
Run this ONCE to create fixed faculty login accounts in MongoDB.

    python seed_admins.py

Edit the FACULTY_ACCOUNTS list below first.
Running this script again is safe: it skips any username that
already exists.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash
from flask_pymongo import PyMongo
from flask import Flask

from config import Config

FACULTY_ACCOUNTS = [
    {"username": "YRP", "password": "YRP@KDP"},
    {"username": "NAP", "password": "NAP@KDP"},
    {"username": "MRT", "password": "MRT@KDP"},
    {"username": "NJP", "password": "NJP@KDP"},
    {"username": "CDP", "password": "CDP@KDP"},
]

app = Flask(__name__)
app.config.from_object(Config)
mongo = PyMongo(app)
db = mongo.db

with app.app_context():
    for acc in FACULTY_ACCOUNTS:
        existing = db.users.find_one({"username": acc["username"]})
        if existing:
            print(f"  - '{acc['username']}' already exists, skipped.")
            continue
        db.users.insert_one({
            "username": acc["username"],
            "password": generate_password_hash(acc["password"]),
            "role": "admin",
            "created_at": datetime.utcnow(),
        })
        print(f"  + created '{acc['username']}'")

print("\nDone. These are now valid logins at /login.")

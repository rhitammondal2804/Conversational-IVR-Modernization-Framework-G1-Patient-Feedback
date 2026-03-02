# backend/database.py

import sqlite3
from datetime import datetime

conn = sqlite3.connect("feedback.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    category TEXT,
    rating TEXT,
    timestamp TEXT
)
""")
conn.commit()


def save_feedback(session_id, category, rating):
    timestamp = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO feedback (session_id, category, rating, timestamp)
    VALUES (?, ?, ?, ?)
    """, (session_id, category, rating, timestamp))
    conn.commit()
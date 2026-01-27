import sqlite3
from pathlib import Path

db_path = Path("data/app.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_events';")
rows = cur.fetchall()

print(rows)

conn.close()

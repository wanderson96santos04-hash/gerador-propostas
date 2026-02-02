import sqlite3

conn = sqlite3.connect("data/app.db")
cur = conn.cursor()

print("Tabelas:")
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row)

conn.close()

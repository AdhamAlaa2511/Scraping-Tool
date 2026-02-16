import sqlite3
import json

conn = sqlite3.connect('competitor_data.db')
cursor = conn.cursor()

cursor.execute("SELECT metadata FROM snapshots ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(row[0])

conn.close()

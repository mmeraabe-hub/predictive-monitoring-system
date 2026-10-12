import sqlite3

conn = sqlite3.connect("predictive_monitoring.db")

tables = conn.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
AND name LIKE 'itt_%'
ORDER BY name
""").fetchall()

print("ITT Tables:")
for table in tables:
    print(table[0])

conn.close()
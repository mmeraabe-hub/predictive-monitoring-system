import sqlite3

conn = sqlite3.connect("predictive_monitoring.db")

count = conn.execute(
    "SELECT COUNT(*) FROM itt_indicator_master"
).fetchone()[0]

print("Indicator Count =", count)

conn.close()
import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    rows = conn.execute(
        """
        SELECT
            Project,
            COUNT(*) AS Records
        FROM dashboard_data
        GROUP BY Project
        ORDER BY Project
        """
    ).fetchall()

    print("Projects currently in production:\n")

    for row in rows:
        print(row)

finally:
    conn.close()
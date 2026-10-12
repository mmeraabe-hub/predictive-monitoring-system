import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    rows = conn.execute(
        """
        SELECT DISTINCT
            Project
        FROM dashboard_data
        ORDER BY Project
        """
    ).fetchall()

    print(
        "Projects in Production"
    )

    for row in rows:
        print(row[0])

finally:

    conn.close()
import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    total = conn.execute(
        """
        SELECT COUNT(DISTINCT IndicatorID)
        FROM dashboard_data
        """
    ).fetchone()[0]

    print(
        "Distinct indicators:",
        total
    )

finally:

    conn.close()
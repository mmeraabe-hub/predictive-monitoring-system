import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    rows = conn.execute(
        """
        SELECT
            IndicatorID,
            Year,
            Quarter
        FROM dashboard_data
        WHERE IndicatorID = 'GG_112'
        ORDER BY Year, Quarter
        """
    ).fetchall()

    print(
        "Production rows:"
    )

    for row in rows:
        print(row)

finally:

    conn.close()
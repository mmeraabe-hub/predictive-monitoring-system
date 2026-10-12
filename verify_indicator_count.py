import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    total_indicators = conn.execute(
        """
        SELECT
            COUNT(DISTINCT IndicatorID)
        FROM dashboard_data
        """
    ).fetchone()[0]

    gg112_rows = conn.execute(
        """
        SELECT
            COUNT(*)
        FROM dashboard_data
        WHERE IndicatorID = 'GG_112'
        """
    ).fetchone()[0]

    print(
        "Distinct indicators:",
        total_indicators
    )

    print(
        "GG_112 rows:",
        gg112_rows
    )

finally:

    conn.close()
import sqlite3
import pandas as pd

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    df = pd.read_sql_query(
        """
        SELECT
            IndicatorID,
            IndicatorName,
            Project,
            Year,
            Quarter
        FROM dashboard_data_staging
        WHERE IndicatorID IN (
            'GG_112',
            'Forgive_001'
        )
        ORDER BY
            IndicatorID,
            Year,
            Quarter
        """,
        conn,
    )

    if df.empty:
        print(
            "No matching indicators found in dashboard_data_staging."
        )

    else:
        print(
            df.to_string(
                index=False
            )
        )

finally:

    conn.close()
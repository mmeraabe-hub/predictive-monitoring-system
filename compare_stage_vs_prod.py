import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    staging = conn.execute(
        """
        SELECT COUNT(*)
        FROM dashboard_data_staging
        """
    ).fetchone()[0]

    production = conn.execute(
        """
        SELECT COUNT(*)
        FROM dashboard_data
        """
    ).fetchone()[0]

    print(
        "Staging:",
        staging
    )

    print(
        "Production:",
        production
    )

finally:

    conn.close()
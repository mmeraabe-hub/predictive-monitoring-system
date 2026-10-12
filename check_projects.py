import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    prod_projects = conn.execute(
        """
        SELECT COUNT(DISTINCT Project)
        FROM dashboard_data
        """
    ).fetchone()[0]

    prod_indicators = conn.execute(
        """
        SELECT COUNT(DISTINCT IndicatorID)
        FROM dashboard_data
        """
    ).fetchone()[0]

    prod_rows = conn.execute(
        """
        SELECT COUNT(*)
        FROM dashboard_data
        """
    ).fetchone()[0]

    print("Production Projects :", prod_projects)
    print("Production Indicators:", prod_indicators)
    print("Production Rows :", prod_rows)

finally:

    conn.close()
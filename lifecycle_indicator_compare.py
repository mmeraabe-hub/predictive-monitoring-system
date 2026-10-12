import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    production_indicators = conn.execute(
        """
        SELECT COUNT(DISTINCT IndicatorID)
        FROM dashboard_data
        """
    ).fetchone()[0]

    staging_indicators = conn.execute(
        """
        SELECT COUNT(DISTINCT IndicatorID)
        FROM dashboard_data_staging
        """
    ).fetchone()[0]

    production_ids = {
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT IndicatorID
            FROM dashboard_data
            """
        ).fetchall()
    }

    staging_ids = {
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT IndicatorID
            FROM dashboard_data_staging
            """
        ).fetchall()
    }

    new_indicators = sorted(
        staging_ids - production_ids
    )

    print(
        "Production Indicators:",
        production_indicators
    )

    print(
        "Staging Indicators:",
        staging_indicators
    )

    print(
        "Indicator Change:",
        staging_indicators
        - production_indicators
    )

    print(
        "\nNew Indicators Added:"
    )

    if not new_indicators:
        print("None")

    else:
        for indicator in new_indicators:
            print(
                f" - {indicator}"
            )

finally:

    conn.close()
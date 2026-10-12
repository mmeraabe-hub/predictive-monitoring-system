import sqlite3

import pandas as pd


connection = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    query = """
        SELECT
            COUNT(*) AS ForecastRecords,
            MIN(ForecastAchievementRatio) AS MinimumForecast,
            MAX(ForecastAchievementRatio) AS MaximumForecast,
            AVG(ForecastAchievementRatio) AS AverageForecast
        FROM horizon_forecast
        WHERE ForecastHorizon = ?
    """

    results = pd.read_sql_query(
        query,
        connection,
        params=(
            "LoP",
        )
    )

    print(
        results.to_string(
            index=False
        )
    )

finally:

    connection.close()
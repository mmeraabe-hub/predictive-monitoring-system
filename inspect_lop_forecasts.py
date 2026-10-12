import sqlite3

import pandas as pd


DATABASE_FILE = "predictive_monitoring.db"


connection = sqlite3.connect(
    DATABASE_FILE
)

try:

    print()
    print("1. EXTREME SOURCE RECORDS")
    print("=" * 70)

    source_query = """
        SELECT
            Project,
            IndicatorID,
            IndicatorName,
            Unit,
            LoPTarget,
            CumulativeActual,
            LoPProgress,
            LoPTimeProgress,
            LoPForecastRatio
        FROM dashboard_data
        WHERE IndicatorID IN (?, ?)
        ORDER BY
            IndicatorID,
            PeriodIndex DESC
    """

    source_records = pd.read_sql_query(
        source_query,
        connection,
        params=(
            "RFSA_027",
            "RFSA_081"
        )
    )

    print(
        source_records
        .head(30)
        .to_string(
            index=False
        )
    )


    print()
    print("2. EXTREME LOP RECORD COUNTS")
    print("=" * 70)

    count_query = """
        SELECT
            COUNT(*) AS TotalRows,

            SUM(
*               CASE
              *     WHEN LoPProgress > 3
        *           THEN 1
                *   ELSE 0
                END
    *       ) AS Above300Percent,

    *       SUM(
                CASE
 *                  WHEN LoPProgress*> 10
                    THEN 1
  *                 ELSE 0
          *     END
            ) AS Above100*Percent

        FROM dashboard_data
    """

    count_results = pd.read_sql_query(
        count_query,
        connection
    )

    print(
        count_results.to_string(
            index=False
        )
    )


    print()
    print("3. HIGHEST GENERATED LOP ML FORECASTS")
    print("=" * 70)

    forecast_query = """
        SELECT
            ForecastHorizon,
            ForecastModel,
            ProjectID,
            IndicatorID,
            CurrentAchievementRatio,
            ForecastAchievementRatio,
            ForecastGapToTarget
        FROM horizon_forecast
        WHERE ForecastHorizon = ?
        ORDER BY ForecastAchievementRatio DESC
        LIMIT 20
    """

    forecast_results = pd.read_sql_query(
        forecast_query,
        connection,
        params=(
            "LoP",
        )
    )

    print(
        forecast_results.to_string(
            index=False
        )
    )


    print()
    print("4. LOP ML FORECAST RANGE")
    print("=" * 70)

    range_query = """
        SELECT
            COUNT(*) AS ForecastRecords,
            MIN(ForecastAchievementRatio) AS MinimumForecast,
            MAX(ForecastAchievementRatio) AS MaximumForecast,
            AVG(ForecastAchievementRatio) AS AverageForecast
        FROM horizon_forecast
        WHERE ForecastHorizon = ?
    """

    range_results = pd.read_sql_query(
        range_query,
        connection,
        params=(
            "LoP",
        )
    )

    print(
        range_results.to_string(
            index=False
        )
    )

finally:

    connection.close()
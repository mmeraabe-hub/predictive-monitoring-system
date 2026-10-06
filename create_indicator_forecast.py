import sqlite3

from utils.database_utils import DB_FILE


def create_indicator_forecast():

    conn = sqlite3.connect(
        str(DB_FILE)
    )

    try:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        prediction_table_exists = conn.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'prediction_archive'
            """
        ).fetchone()[0]

        if not prediction_table_exists:

            raise RuntimeError(
                "prediction_archive does not exist."
            )

        prediction_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM prediction_archive
            """
        ).fetchone()[0]

        if prediction_count == 0:

            raise RuntimeError(
                "prediction_archive is empty."
            )

        conn.execute(
            """
            DROP TABLE IF EXISTS indicator_forecast
            """
        )

        conn.execute(
            """
            CREATE TABLE indicator_forecast AS

            WITH ranked_forecasts AS (

                SELECT
                    ForecastCreatedUTC,
                    EvaluationTimestampUTC,
                    UploadBatchID,
                    DatasetType,
                    Model,
                    ProjectID,
                    IndicatorID,
                    IndicatorName,
                    Year,
                    Quarter,
                    PeriodIndex,
                    PeriodLabel,
                    CurrentActualValue,
                    PredictedValue,

                    ROW_NUMBER() OVER (
                        PARTITION BY
                            ProjectID,
                            IndicatorID
                        ORDER BY
                            PeriodIndex DESC,
                            ForecastCreatedUTC DESC
                    ) AS ForecastRank

                FROM prediction_archive

                WHERE ForecastStatus = 'Verified'
                  AND CurrentActualValue IS NOT NULL
                  AND PredictedValue IS NOT NULL
            )

            SELECT
                ProjectID,

                IndicatorID,

                IndicatorName,

                Year AS CurrentYear,

                Quarter AS CurrentQuarter,

                PeriodIndex AS CurrentPeriodIndex,

                PeriodLabel AS CurrentPeriodLabel,

                CurrentActualValue AS CurrentValue,

                PredictedValue AS ForecastNextQuarter,

                CASE
                    WHEN Model = 'Naive Persistence'
                    THEN PredictedValue
                    ELSE NULL
                END AS ForecastNextYear,

                CASE
                    WHEN Model = 'Naive Persistence'
                    THEN PredictedValue
                    ELSE NULL
                END AS ForecastLOP,

                DatasetType,

                Model AS ForecastModel,

                CASE
                    WHEN Model = 'Naive Persistence'
                    THEN 'Naive persistence carried forward'
                    ELSE 'Multi-horizon projection not generated'
                END AS ProjectionMethod,

                ForecastCreatedUTC,

                EvaluationTimestampUTC,

                UploadBatchID

            FROM ranked_forecasts

            WHERE ForecastRank = 1
            """
        )

        forecast_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM indicator_forecast
            """
        ).fetchone()[0]

        if forecast_count == 0:

            raise RuntimeError(
                "indicator_forecast was created but contains no rows."
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_indicator_forecast_project
            ON indicator_forecast (
                ProjectID
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_indicator_forecast_indicator
            ON indicator_forecast (
                IndicatorID
            )
            """
        )

        conn.commit()

        print(
            "indicator_forecast created successfully."
        )

        print(
            f"Rows created: {forecast_count}"
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


if __name__ == "__main__":

    create_indicator_forecast()
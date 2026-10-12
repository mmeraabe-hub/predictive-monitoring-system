import sqlite3

import pandas as pd


DATABASE_PATH = "predictive_monitoring.db"


connection = sqlite3.connect(
    DATABASE_PATH
)

try:
    repository_summary = pd.read_sql_query(
        """
        SELECT
            Project,
            ProjectCode,
            COUNT(*) AS IndicatorCount
        FROM itt_indicator_master
        GROUP BY
            Project,
            ProjectCode
        ORDER BY
            Project
        """,
        connection,
    )

    print("")
    print("ITT REPOSITORY BY PROJECT")
    print("=========================")

    if repository_summary.empty:
        print(
            "No indicators were found in "
            "itt_indicator_master."
        )

    else:
        print(
            repository_summary.to_string(
                index=False
            )
        )

    validation_summary = pd.read_sql_query(
        """
        SELECT
            COUNT(*) AS TotalIndicators,

            SUM(
                CASE
                    WHEN IndicatorID IS NULL
                      OR TRIM(IndicatorID) = ''
                    THEN 1
                    ELSE 0
                END
            ) AS MissingIndicatorID,

            SUM(
                CASE
                    WHEN ProjectCode IS NULL
                      OR TRIM(ProjectCode) = ''
                    THEN 1
                    ELSE 0
                END
            ) AS MissingProjectCode,

            SUM(
                CASE
                    WHEN IndicatorName IS NULL
                      OR TRIM(IndicatorName) = ''
                    THEN 1
                    ELSE 0
                END
            ) AS MissingIndicatorName,

            SUM(
                CASE
                    WHEN UnitOfMeasure IS NULL
                      OR TRIM(UnitOfMeasure) = ''
                    THEN 1
                    ELSE 0
                END
            ) AS MissingUnit
        FROM itt_indicator_master
        """,
        connection,
    )

    print("")
    print("REPOSITORY VALIDATION")
    print("=====================")

    print(
        validation_summary.to_string(
            index=False
        )
    )

    sample_indicators = pd.read_sql_query(
        """
        SELECT
            IndicatorID,
            Project,
            ProjectCode,
            IndicatorName,
            UnitOfMeasure,
            LifeProjectYear,
            Baseline,
            ProjectLifeTarget,
            Year1Target,
            Year2Target,
            Year3Target,
            Year4Target,
            Year5Target
        FROM itt_indicator_master
        ORDER BY
            ProjectCode,
            IndicatorID
        LIMIT 10
        """,
        connection,
    )

    print("")
    print("SAMPLE INDICATORS")
    print("=================")

    if sample_indicators.empty:
        print(
            "No sample records are available."
        )

    else:
        print(
            sample_indicators.to_string(
                index=False
            )
        )

finally:
    connection.close()
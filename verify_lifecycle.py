import sqlite3
import pandas as pd

conn = sqlite3.connect("predictive_monitoring.db")

print("\n=== DASHBOARD SUMMARY ===\n")

print(
    pd.read_sql_query(
        """
        SELECT
            COUNT(*) AS TotalRows,
            COUNT(DISTINCT Project) AS ProjectCount,
            COUNT(DISTINCT IndicatorID) AS IndicatorCount
        FROM dashboard_data
        """,
        conn
    )
)

print("\n=== PROJECTS ===\n")

print(
    pd.read_sql_query(
        """
        SELECT
            Project,
            COUNT(*) AS Rows
        FROM dashboard_data
        GROUP BY Project
        ORDER BY Project
        """,
        conn
    )
)

print("\n=== ORIGINAL MODEL REGISTRY ===\n")

print(
    pd.read_sql_query(
        """
        SELECT
            DatasetType,
            Model,
            Version,
            Status
        FROM model_registry
        WHERE DatasetType='Original'
        ORDER BY Model, Version
        """,
        conn
    )
)

print("\n=== LIFECYCLE AUDIT LOG ===\n")

print(
    pd.read_sql_query(
        """
        SELECT *
        FROM model_lifecycle_decision_log
        ORDER BY DecisionID DESC
        LIMIT 10
        """,
        conn
    )
)

conn.close()

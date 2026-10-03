import sqlite3

DB_FILE = "predictive_monitoring.db"
DECISION_ID = 1

conn = sqlite3.connect(
    DB_FILE,
    timeout=30
)

try:
    conn.execute("BEGIN IMMEDIATE")

    audit_row = conn.execute(
        """
        SELECT
            DecisionID,
            RecommendedModel,
            TransactionStatus
        FROM model_lifecycle_decision_log
        WHERE DecisionID = ?
        """,
        (DECISION_ID,)
    ).fetchone()

    if audit_row is None:
        raise RuntimeError(
            f"DecisionID {DECISION_ID} was not found."
        )

    recommended_model = str(
        audit_row[1]
    ).strip()

    transaction_status = str(
        audit_row[2]
    ).strip()

    if transaction_status.lower() != "completed":
        raise RuntimeError(
            "Only a completed lifecycle decision "
            "should be repaired."
        )

    production_after = conn.execute(
        """
        SELECT
            Model,
            Version,
            MAE,
            RMSE
        FROM model_registry
        WHERE lower(trim(DatasetType)) = 'original'
          AND lower(trim(Model)) = lower(trim(?))
          AND lower(trim(Status)) = 'production'
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (recommended_model,)
    ).fetchone()

    if production_after is None:
        raise RuntimeError(
            "The current Original production model "
            "could not be found."
        )

    production_before = conn.execute(
        """
        SELECT
            Model,
            Version
        FROM model_registry
        WHERE lower(trim(DatasetType)) = 'original'
          AND lower(trim(Model)) = lower(trim(?))
          AND lower(trim(Status)) = 'retired'
        ORDER BY
            CASE
                WHEN Version GLOB 'v*'
                THEN CAST(substr(Version, 2) AS REAL)
                ELSE 0
            END DESC,
            rowid DESC
        LIMIT 1
        """,
        (recommended_model,)
    ).fetchone()

    if production_before is None:
        raise RuntimeError(
            "The previous retired Original model "
            "could not be found."
        )

    dashboard_summary = conn.execute(
        """
        SELECT
            COUNT(*) AS TotalRows,
            COUNT(DISTINCT Project) AS ProjectCount
        FROM dashboard_data
        """
    ).fetchone()

    total_rows = int(
        dashboard_summary[0]
    )

    project_count = int(
        dashboard_summary[1]
    )

    update_result = conn.execute(
        """
        UPDATE model_lifecycle_decision_log
        SET
            ProductionModelBefore = ?,
            ProductionVersionBefore = ?,
            RecommendedVersion = ?,
            RecommendedMAE = ?,
            RecommendedRMSE = ?,
            ProductionModelAfter = ?,
            ProductionVersionAfter = ?,
            DashboardRowsBefore = ?,
            DashboardRowsAfter = ?,
            ProjectsBefore = ?,
            ProjectsAfter = ?
        WHERE DecisionID = ?
        """,
        (
            str(production_before[0]).strip(),
            str(production_before[1]).strip(),
            str(production_after[1]).strip(),
            production_after[2],
            production_after[3],
            str(production_after[0]).strip(),
            str(production_after[1]).strip(),
            total_rows,
            total_rows,
            project_count,
            project_count,
            DECISION_ID,
        )
    )

    if update_result.rowcount != 1:
        raise RuntimeError(
            "The audit record was not updated exactly once."
        )

    remaining_nulls = conn.execute(
        """
        SELECT
            ProductionModelBefore,
            ProductionVersionBefore,
            RecommendedVersion,
            RecommendedMAE,
            RecommendedRMSE,
            ProductionModelAfter,
            ProductionVersionAfter,
            DashboardRowsBefore,
            DashboardRowsAfter,
            ProjectsBefore,
            ProjectsAfter
        FROM model_lifecycle_decision_log
        WHERE DecisionID = ?
        """,
        (DECISION_ID,)
    ).fetchone()

    if remaining_nulls is None:
        raise RuntimeError(
            "The repaired audit record could not be verified."
        )

    if any(value is None for value in remaining_nulls):
        raise RuntimeError(
            "Audit repair validation failed because "
            "one or more required fields remain empty."
        )

    conn.commit()

    print("Audit record repaired successfully.")
    print()
    print(
        "Production before:",
        production_before[0],
        production_before[1]
    )
    print(
        "Recommended version:",
        production_after[1]
    )
    print(
        "Recommended MAE:",
        production_after[2]
    )
    print(
        "Recommended RMSE:",
        production_after[3]
    )
    print(
        "Production after:",
        production_after[0],
        production_after[1]
    )
    print(
        "Dashboard rows:",
        total_rows
    )
    print(
        "Projects:",
        project_count
    )

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()

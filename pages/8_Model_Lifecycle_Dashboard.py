
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from utils.database_utils import DB_FILE

from utils.approved_itt_etl_clean import (
    load_approved_batch,
    reconstruct_uploaded_itt,
    transform_itt_to_longitudinal,
    build_dashboard_features,
    upsert_dashboard_data,
)
# ============================================================
# LIFECYCLE GOVERNANCE TABLE
# ============================================================

def initialize_lifecycle_decision_log():

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            model_lifecycle_decision_log (
                DecisionID INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                DecisionTimestampUTC TEXT
                    NOT NULL,

                UploadBatchID TEXT
                    NOT NULL,

                Action TEXT
                    NOT NULL,

                DatasetType TEXT
                    NOT NULL,

                ProductionModelBefore TEXT,

                ProductionVersionBefore TEXT,

                RecommendedModel TEXT
                    NOT NULL,

                RecommendedVersion TEXT,

                RecommendedMAE REAL,

                RecommendedRMSE REAL,

                ReviewerName TEXT
                    NOT NULL,

                DecisionReason TEXT
                    NOT NULL,

                ProductionModelAfter TEXT,

                ProductionVersionAfter TEXT,

                DashboardRowsBefore INTEGER,

                DashboardRowsAfter INTEGER,

                ProjectsBefore INTEGER,

                ProjectsAfter INTEGER,

                TransactionStatus TEXT
                    NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_lifecycle_decision_batch
            ON model_lifecycle_decision_log (
                UploadBatchID
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_lifecycle_decision_timestamp
            ON model_lifecycle_decision_log (
                DecisionTimestampUTC
            )
            """
        )

        conn.commit()

    finally:

        conn.close()


initialize_lifecycle_decision_log()
# ============================================================
# CONTROLLED LIFECYCLE TRANSACTION HELPERS
# ============================================================

def sqlite_safe_value(
    value
):

    if pd.isna(
        value
    ):
        return None

    if hasattr(
        value,
        "item"
    ):
        try:
            return value.item()
        except Exception:
            pass

    return value


def load_original_production_model(
    conn
):

    production_rows = conn.execute(
        """
        SELECT
            Model,
            Version
        FROM model_registry
        WHERE DatasetType = 'Original'
          AND lower(trim(Status)) = 'production'
        ORDER BY rowid DESC
        """
    ).fetchall()

    if len(production_rows) != 1:
        raise RuntimeError(
            "The Original track must contain exactly "
            "one Production model."
        )

    return {
        "Model":
            str(
                production_rows[0][0]
            ),

        "Version":
            str(
                production_rows[0][1]
            ),
    }


def load_recommended_original_candidate(
    conn,
    recommended_model
):

    normalized_model = str(
        recommended_model
    ).strip()

    candidate_rows = conn.execute(
        """
        SELECT
            Model,
            Version,
            MAE,
            RMSE,
            Status
        FROM model_registry
        WHERE lower(trim(DatasetType)) = 'original'
          AND lower(trim(Model)) = lower(trim(?))
          AND lower(trim(Status)) = 'candidate'
        ORDER BY
            TrainingDate DESC,
            rowid DESC
        LIMIT 1
        """,
        (
            normalized_model,
        ),
    ).fetchall()

    if candidate_rows:

        return {
            "Model":
                str(
                    candidate_rows[0][0]
                ).strip(),

            "Version":
                str(
                    candidate_rows[0][1]
                ).strip(),

            "MAE":
                candidate_rows[0][2],

            "RMSE":
                candidate_rows[0][3],

            "Status":
                str(
                    candidate_rows[0][4]
                ).strip(),
        }

    production_rows = conn.execute(
        """
        SELECT
            Model,
            Version,
            MAE,
            RMSE,
            Status
        FROM model_registry
        WHERE lower(trim(DatasetType)) = 'original'
          AND lower(trim(Model)) = lower(trim(?))
          AND lower(trim(Status)) = 'production'
        ORDER BY
            TrainingDate DESC,
            rowid DESC
        LIMIT 1
        """,
        (
            normalized_model,
        ),
    ).fetchall()

    if production_rows:

        return {
            "Model":
                str(
                    production_rows[0][0]
                ).strip(),

            "Version":
                str(
                    production_rows[0][1]
                ).strip(),

            "MAE":
                production_rows[0][2],

            "RMSE":
                production_rows[0][3],

            "Status":
                str(
                    production_rows[0][4]
                ).strip(),
        }

    available_candidates = conn.execute(
        """
        SELECT
            Model,
            Version,
            Status
        FROM model_registry
        WHERE lower(trim(DatasetType)) = 'original'
          AND lower(trim(Status)) = 'candidate'
        ORDER BY
            Model,
            Version
        """
    ).fetchall()

    raise RuntimeError(
        "No Original-track Candidate version exists for "
        f"the recommended model '{normalized_model}'. "
        "Available Original candidates: "
        f"{available_candidates}"
    )

    candidate_rows = conn.execute(
        """
        SELECT
            Model,
            Version,
            MAE,
            RMSE
        FROM model_registry
        WHERE DatasetType = 'Original'
          AND Model = ?
          AND lower(trim(Status)) = 'candidate'
        ORDER BY
            TrainingDate DESC,
            rowid DESC
        LIMIT 1
        """,
        (
            recommended_model,
        ),
    ).fetchall()

    if not candidate_rows:
        raise RuntimeError(
            "No Original-track Candidate version exists "
            "for the recommended model."
        )

    return {
        "Model":
            str(
                candidate_rows[0][0]
            ),

        "Version":
            str(
                candidate_rows[0][1]
            ),

        "MAE":
            candidate_rows[0][2],

        "RMSE":
            candidate_rows[0][3],
    }


def upsert_dashboard_data_in_transaction(
    conn,
    dashboard_df
):

    if dashboard_df is None:
        raise ValueError(
            "dashboard_df cannot be None."
        )

    if dashboard_df.empty:
        raise ValueError(
            "dashboard_df contains no records."
        )

    incoming_data = (
        dashboard_df.copy()
    )

    key_columns = [
        "Project",
        "IndicatorID",
        "Year",
        "Quarter",
    ]

    missing_keys = [
        column
        for column in key_columns
        if column not in incoming_data.columns
    ]

    if missing_keys:
        raise ValueError(
            "Required dashboard key columns are missing: "
            + ", ".join(
                missing_keys
            )
        )

    incoming_data["Project"] = (
        incoming_data["Project"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    incoming_data["IndicatorID"] = (
        incoming_data["IndicatorID"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    incoming_data["Year"] = pd.to_numeric(
        incoming_data["Year"],
        errors="raise",
    ).astype(int)

    incoming_data["Quarter"] = pd.to_numeric(
        incoming_data["Quarter"],
        errors="raise",
    ).astype(int)

    if incoming_data["Project"].eq("").any():
        raise ValueError(
            "Incoming data contains empty Project values."
        )

    if incoming_data["IndicatorID"].eq("").any():
        raise ValueError(
            "Incoming data contains empty IndicatorID values."
        )

    incoming_duplicates = int(
        incoming_data.duplicated(
            subset=key_columns,
            keep=False,
        ).sum()
    )

    if incoming_duplicates > 0:
        raise ValueError(
            "The approved dataset contains "
            f"{incoming_duplicates:,} duplicate "
            "Project–Indicator–Year–Quarter keys."
        )

    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'dashboard_data'
        """
    ).fetchone()

    if table_exists is None:
        raise RuntimeError(
            "dashboard_data does not exist."
        )

    existing_columns = [
        row[1]
        for row in conn.execute(
            """
            PRAGMA table_info(
                dashboard_data
            )
            """
        ).fetchall()
    ]

    incoming_columns = (
        incoming_data.columns.tolist()
    )

    if existing_columns != incoming_columns:
        raise RuntimeError(
            "The incoming dashboard schema does not match "
            "dashboard_data. "
            f"Existing columns: {len(existing_columns)}; "
            f"incoming columns: {len(incoming_columns)}."
        )

    rows_before = conn.execute(
        """
        SELECT COUNT(*)
        FROM dashboard_data
        """
    ).fetchone()[0]

    projects_before = conn.execute(
        """
        SELECT COUNT(DISTINCT Project)
        FROM dashboard_data
        """
    ).fetchone()[0]

    delete_sql = """
        DELETE FROM dashboard_data
        WHERE Project = ?
          AND IndicatorID = ?
          AND Year = ?
          AND Quarter = ?
    """

    delete_keys = [
        tuple(
            sqlite_safe_value(
                value
            )
            for value in row
        )
        for row in incoming_data[
            key_columns
        ].itertuples(
            index=False,
            name=None,
        )
    ]

    matching_rows_replaced = 0

    for key in delete_keys:

        matching_rows_replaced += int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM dashboard_data
                WHERE Project = ?
                  AND IndicatorID = ?
                  AND Year = ?
                  AND Quarter = ?
                """,
                key,
            ).fetchone()[0]
        )

    conn.executemany(
        delete_sql,
        delete_keys,
    )

    quoted_columns = ", ".join(
        f'"{column}"'
        for column in incoming_columns
    )

    placeholders = ", ".join(
        ["?"] * len(
            incoming_columns
        )
    )

    insert_sql = (
        'INSERT INTO "dashboard_data" '
        f"({quoted_columns}) "
        f"VALUES ({placeholders})"
    )

    insert_rows = [
        tuple(
            sqlite_safe_value(
                value
            )
            for value in row
        )
        for row in incoming_data.itertuples(
            index=False,
            name=None,
        )
    ]

    conn.executemany(
        insert_sql,
        insert_rows,
    )

    duplicate_keys_after = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                Project,
                IndicatorID,
                Year,
                Quarter,
                COUNT(*) AS RecordCount
            FROM dashboard_data
            GROUP BY
                Project,
                IndicatorID,
                Year,
                Quarter
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    if duplicate_keys_after > 0:
        raise RuntimeError(
            "Post-promotion validation found "
            f"{duplicate_keys_after:,} duplicate keys."
        )

    rows_after = conn.execute(
        """
        SELECT COUNT(*)
        FROM dashboard_data
        """
    ).fetchone()[0]

    projects_after = conn.execute(
        """
        SELECT COUNT(DISTINCT Project)
        FROM dashboard_data
        """
    ).fetchone()[0]

    expected_rows = (
        rows_before
        - matching_rows_replaced
        + len(
            incoming_data
        )
    )

    if rows_after != expected_rows:
        raise RuntimeError(
            "Dashboard row validation failed. "
            f"Expected {expected_rows:,} records but "
            f"found {rows_after:,}."
        )

    return {
        "InsertedRows":
            len(
                incoming_data
            ),

        "MatchingRowsReplaced":
            matching_rows_replaced,

        "RowsBefore":
            rows_before,

        "RowsAfter":
            rows_after,

        "ProjectsBefore":
            projects_before,

        "ProjectsAfter":
            projects_after,

        "LoadedProjects":
            sorted(
                incoming_data[
                    "Project"
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
    }


def execute_governance_decision(
    action,
    reviewer_name,
    decision_reason,
    approved_summary,
    recommended
):

    reviewer_name = str(
        reviewer_name
    ).strip()

    decision_reason = str(
        decision_reason
    ).strip()

    if action not in [
        "Promote Candidate",
        "Reject Candidate",
    ]:
        raise ValueError(
            "Select Promote Model or "
            "Reject Candidate."
        )

    if not reviewer_name:
        raise ValueError(
            "Reviewer Name is required."
        )

    if not decision_reason:
        raise ValueError(
            "Decision Rationale is required."
        )

    upload_batch_id = str(
        approved_summary[
            "UploadBatchID"
        ]
    )

    recommended_model = str(
        recommended[
            "Model"
        ]
    )

    recommended_mae = float(
        recommended[
            "MAE"
        ]
    )

    recommended_rmse = float(
        recommended[
            "RMSE"
        ]
    )
    decision_timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn = sqlite3.connect(
        DB_FILE,
        timeout=30
    )

    try:

        try:

            conn.execute(
                "BEGIN IMMEDIATE"
            )

        except sqlite3.OperationalError:

            raise RuntimeError(
                "The database is currently locked. "
                "Close DB Browser, SQLite viewers, extra Streamlit tabs, "
                "or other applications using predictive_monitoring.db "
                "and try again."
            )

        production_before = (
            load_original_production_model(
                conn
            )
        )
        candidate = (
            load_recommended_original_candidate(
                conn=conn,
                recommended_model=(
                    recommended_model
                ),
            )
        )

        candidate_status = str(
            candidate.get(
                "Status",
                ""
            )
        ).strip().lower()

        model_already_production = (
            candidate_status == "production"
        )
       
        

        dashboard_result = {
            "RowsBefore":
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM dashboard_data
                    """
                ).fetchone()[0],

            "RowsAfter":
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM dashboard_data
                    """
                ).fetchone()[0],

            "ProjectsBefore":
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT Project)
                    FROM dashboard_data
                    """
                ).fetchone()[0],

            "ProjectsAfter":
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT Project)
                    FROM dashboard_data
                    """
                ).fetchone()[0],

            "InsertedRows":
                0,

            "MatchingRowsReplaced":
                0,

            "LoadedProjects":
                [],
        }

        if action == "Promote Candidate":

            staging_dashboard = pd.read_sql_query(
                """
                SELECT *
                FROM dashboard_data_staging
                """,
                conn
            )

            if staging_dashboard.empty:
                raise RuntimeError(
                    "No candidate dataset exists in dashboard_data_staging."
                )

            dashboard_result = (
                upsert_dashboard_data_in_transaction(
                    conn=conn,
                    dashboard_df=staging_dashboard,
                )
            )

            model_performance_staging = pd.read_sql_query(
                """
                SELECT *
                FROM model_performance_staging
                """,
                conn
            )

            if model_performance_staging.empty:
                raise RuntimeError(
                    "No candidate model results exist in model_performance_staging."
                )

            model_performance_staging.to_sql(
                "model_performance",
                conn,
                if_exists="replace",
                index=False
            )
            forecast_tables = [
                (
                    "prediction_archive_staging",
                    "prediction_archive"
                ),
                (
                    "forecast_verification_metrics_staging",
                    "forecast_verification_metrics"
                ),
                (
                    "forecast_verification_by_project_staging",
                    "forecast_verification_by_project"
                ),
            ]

            for staging_table, production_table in forecast_tables:

                forecast_staging_data = pd.read_sql_query(
                    f"""
                    SELECT *
                    FROM {staging_table}
                    """,
                    conn
                )

                forecast_staging_data.to_sql(
                    production_table,
                    conn,
                    if_exists="replace",
                    index=False
                )

            conn.execute(
                """
                UPDATE training_run_staging
                SET Status = 'Promoted'
                """
            )
            if model_already_production:

                production_after = {
                    "Model":
                        production_before[
                            "Model"
                        ],

                    "Version":
                        production_before[
                            "Version"
                        ],
                }

            else:

                retired_update = conn.execute(
                    """
                    UPDATE model_registry
                    SET Status = 'Retired'
                    WHERE lower(trim(DatasetType)) = 'original'
                      AND Model = ?
                      AND Version = ?
                      AND lower(trim(Status)) = 'production'
                    """,
                    (
                        production_before[
                            "Model"
                        ],
                        production_before[
                            "Version"
                        ],
                    ),
                )

                if retired_update.rowcount != 1:
                    raise RuntimeError(
                        "The current Original production model "
                        "could not be retired safely."
                    )

                promoted_update = conn.execute(
                    """
                    UPDATE model_registry
                    SET Status = 'Production'
                    WHERE lower(trim(DatasetType)) = 'original'
                      AND Model = ?
                      AND Version = ?
                      AND lower(trim(Status)) = 'candidate'
                    """,
                    (
                        candidate[
                            "Model"
                        ],
                        candidate[
                            "Version"
                        ],
                    ),
                )

                if promoted_update.rowcount != 1:
                    raise RuntimeError(
                        "The recommended Candidate could not "
                        "be promoted safely."
                    )

                production_after = {
                    "Model":
                        candidate[
                            "Model"
                        ],

                    "Version":
                        candidate[
                            "Version"
                        ],
                }
            
            audit_action = (
                "Promote"
            )

        else:

            if model_already_production:
                raise RuntimeError(
                    "The recommended model is already in production "
                    "and cannot be rejected as a Candidate."
                )

            declined_update = conn.execute(
                """
                UPDATE model_registry
                SET Status = 'Declined'
                WHERE DatasetType = 'Original'
                  AND Model = ?
                  AND Version = ?
                  AND lower(trim(Status)) = 'candidate'
                """,
                (
                    candidate[
                        "Model"
                    ],
                    candidate[
                        "Version"
                    ],
                ),
            )

            if declined_update.rowcount != 1:
                raise RuntimeError(
                    "The recommended Candidate could not "
                    "be declined safely."
                )

            production_after = (
                production_before.copy()
            )

            audit_action = (
                "Decline"
            )

        final_production_rows = conn.execute(
            """
            SELECT
                Model,
                Version
            FROM model_registry
            WHERE DatasetType = 'Original'
              AND lower(trim(Status)) = 'production'
            """
        ).fetchall()

        if len(
            final_production_rows
        ) != 1:
            raise RuntimeError(
                "The Original track must contain exactly "
                "one Production model after the decision."
            )

        if (
            str(
                final_production_rows[0][0]
            )
            != production_after[
                "Model"
            ]
            or
            str(
                final_production_rows[0][1]
            )
            != production_after[
                "Version"
            ]
        ):
            raise RuntimeError(
                "Post-decision production-model "
                "verification failed."
            )

        conn.execute(
            """
            INSERT INTO model_lifecycle_decision_log (
                DecisionTimestampUTC,
                UploadBatchID,
                Action,
                DatasetType,
                ProductionModelBefore,
                ProductionVersionBefore,
                RecommendedModel,
                RecommendedVersion,
                RecommendedMAE,
                RecommendedRMSE,
                ReviewerName,
                DecisionReason,
                ProductionModelAfter,
                ProductionVersionAfter,
                DashboardRowsBefore,
                DashboardRowsAfter,
                ProjectsBefore,
                ProjectsAfter,
                TransactionStatus
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                decision_timestamp,
                upload_batch_id,
                audit_action,
                "Original",

                production_before[
                    "Model"
                ],

                production_before[
                    "Version"
                ],

                candidate[
                    "Model"
                ],

                candidate[
                    "Version"
                ],

                candidate[
                    "MAE"
                ],

                candidate[
                    "RMSE"
                ],

                reviewer_name,
                decision_reason,

                production_after[
                    "Model"
                ],

                production_after[
                    "Version"
                ],

                dashboard_result[
                    "RowsBefore"
                ],

                dashboard_result[
                    "RowsAfter"
                ],

                dashboard_result[
                    "ProjectsBefore"
                ],

                dashboard_result[
                    "ProjectsAfter"
                ],

                "Completed",
            ),
        )

        conn.commit()

        return {
            "Action":
                audit_action,

            "UploadBatchID":
                upload_batch_id,

            "ProductionBefore":
                (
                    production_before[
                        "Model"
                    ]
                    + " "
                    + production_before[
                        "Version"
                    ]
                ),

            "RecommendedCandidate":
                (
                    candidate[
                        "Model"
                    ]
                    + " "
                    + candidate[
                        "Version"
                    ]
                ),

            "ProductionAfter":
                (
                    production_after[
                        "Model"
                    ]
                    + " "
                    + production_after[
                        "Version"
                    ]
                ),

            "DashboardRowsBefore":
                dashboard_result[
                    "RowsBefore"
                ],

            "DashboardRowsAfter":
                dashboard_result[
                    "RowsAfter"
                ],

            "ProjectsBefore":
                dashboard_result[
                    "ProjectsBefore"
                ],

            "ProjectsAfter":
                dashboard_result[
                    "ProjectsAfter"
                ],

            "LoadedProjects":
                dashboard_result[
                    "LoadedProjects"
                ],

            "TimestampUTC":
                decision_timestamp,

            "Status":
                "Completed",
        }

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Model Lifecycle Management",
    page_icon="🔄",
    layout="wide",
)

st.title(
    "Model Lifecycle Management"
)

st.caption(
    "Review the latest approved portfolio dataset, "
    "inspect model-training results, and make a controlled "
    "production-model decision."
)


# ============================================================
# DATA LOADING
# ============================================================

def load_latest_approved_batch():

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        approved_batches = pd.read_sql_query(
            """
            SELECT
                UploadBatchID,
                UploadTimestampUTC,
                FileName,
                RowCount,
                ColumnCountMaximum,
                UploadStatus,
                ReviewNotes,
                ApprovedTimestampUTC,
                ApprovedBy
            FROM itt_upload_batches
            WHERE lower(trim(UploadStatus)) = 'approved'
            ORDER BY
                ApprovedTimestampUTC DESC,
                UploadTimestampUTC DESC
            LIMIT 1
            """,
            conn,
        )

    finally:

        conn.close()

    if approved_batches.empty:
        return None

    return approved_batches.iloc[0]


def build_approved_dataset_summary():

    approved_batch = (
        load_latest_approved_batch()
    )

    if approved_batch is None:
        return None

    upload_batch_id = str(
        approved_batch[
            "UploadBatchID"
        ]
    )

    batch_row, staged_rows = (
        load_approved_batch(
            upload_batch_id=upload_batch_id,
            database_file=DB_FILE,
        )
    )

    if staged_rows.empty:
        raise ValueError(
            "The approved batch contains no staged records."
        )

    itt_df = reconstruct_uploaded_itt(
        staged_rows
    )

    if itt_df.empty:
        raise ValueError(
            "The approved ITT could not be reconstructed."
        )

    longitudinal_df = (
        transform_itt_to_longitudinal(
            itt_df
        )
    )

    if longitudinal_df.empty:
        raise ValueError(
            "The longitudinal transformation produced "
            "no records."
        )

    dashboard_df = (
        build_dashboard_features(
            longitudinal_df,
            itt_df,
        )
    )

    if dashboard_df.empty:
        raise ValueError(
            "Dashboard feature construction produced "
            "no records."
        )

    duplicate_keys = int(
        dashboard_df.duplicated(
            subset=[
                "Project",
                "IndicatorID",
                "Year",
                "Quarter",
            ]
        ).sum()
    )

    return {
        "Batch":
            approved_batch,

        "ITTData":
            itt_df,

        "LongitudinalData":
            longitudinal_df,

        "DashboardData":
            dashboard_df,

        "UploadBatchID":
            upload_batch_id,

        "FileName":
            str(
                approved_batch[
                    "FileName"
                ]
            ),

        "Status":
            str(
                approved_batch[
                    "UploadStatus"
                ]
            ),

        "ApprovedTimestampUTC":
            approved_batch[
                "ApprovedTimestampUTC"
            ],

        "ApprovedBy":
            approved_batch[
                "ApprovedBy"
            ],

        "ProjectCount":
            int(
                dashboard_df[
                    "Project"
                ].nunique()
            ),

        "IndicatorCount":
            int(
                dashboard_df[
                    "IndicatorID"
                ].nunique()
            ),

        "ITTRecordCount":
            len(
                itt_df
            ),

        "LongitudinalRecordCount":
            len(
                longitudinal_df
            ),

        "DashboardRecordCount":
            len(
                dashboard_df
            ),

        "DuplicateKeys":
            duplicate_keys,
    }
# ============================================================
# CANDIDATE EVALUATION SUMMARY
# ============================================================
# ============================================================
# CANDIDATE EVALUATION SUMMARY
# ============================================================

st.divider()

st.subheader(
    "Candidate Evaluation Summary"
)

st.caption(
    "The approved dataset has been processed and evaluated "
    "in the staging environment. Candidate results remain "
    "separate from production until a reviewer authorizes "
    "promotion."
)

conn = sqlite3.connect(
    DB_FILE
)

try:

    candidate_run = pd.read_sql_query(
        """
        SELECT *
        FROM training_run_staging
        ORDER BY RunFinishedUTC DESC
        LIMIT 1
        """,
        conn
    )

    candidate_performance = pd.read_sql_query(
        """
        SELECT *
        FROM model_performance_staging
        """,
        conn
    )

finally:

    conn.close()

if candidate_run.empty:

    st.warning(
        "No candidate evaluation run is available."
    )

    st.info(
        "Approve a reviewed ITT for evaluation before "
        "making a lifecycle governance decision."
    )

    st.stop()

if candidate_performance.empty:

    st.warning(
        "No candidate model-performance results are available."
    )

    st.stop()

candidate = candidate_run.iloc[0]

candidate_status_col1, candidate_status_col2, candidate_status_col3 = (
    st.columns(3)
)

candidate_status_col1.metric(
    "Candidate Status",
    str(
        candidate[
            "Status"
        ]
    )
)

candidate_status_col2.metric(
    "Forecasting Models",
    f"{candidate_performance['Model'].nunique():,}"
)

candidate_status_col3.metric(
    "Evaluation Completed UTC",
    str(
        candidate[
            "RunFinishedUTC"
        ]
    )
)

st.markdown(
    "#### Candidate Dataset Impact"
)

project_col1, project_col2, project_col3 = (
    st.columns(3)
)

project_col1.metric(
    "Projects Before",
    f"{int(candidate['ProjectsBefore']):,}"
)

project_col2.metric(
    "Projects After",
    f"{int(candidate['ProjectsAfter']):,}"
)

project_col3.metric(
    "Project Change",
    (
        f"{int(candidate['ProjectsAfter']) - int(candidate['ProjectsBefore']):+d}"
    )
)

row_col1, row_col2, row_col3 = (
    st.columns(3)
)

row_col1.metric(
    "Production Rows",
    f"{int(candidate['DashboardRowsBefore']):,}"
)

row_col2.metric(
    "Candidate Rows",
    f"{int(candidate['DashboardRowsAfter']):,}"
)

row_col3.metric(
    "Net Rows Added",
    f"{int(candidate['RowsAdded']):,}"
)

split_col1, split_col2 = (
    st.columns(2)
)

split_col1.metric(
    "Training Rows per Track",
    f"{int(candidate['TrainingRows']):,}"
)

split_col2.metric(
    "Testing Rows per Track",
    f"{int(candidate['TestingRows']):,}"
)

st.caption(
    "The Original and Capped tracks use the same underlying "
    "candidate observations with different target treatments. "
    "Training and testing rows are therefore reported per track "
    "and should not be added together."
)

original_recommendation = (
    candidate_performance[
        candidate_performance[
            "AnalysisTrack"
        ]
        .astype(str)
        .str.contains(
            "Original",
            case=False,
            na=False
        )
        &
        candidate_performance[
            "IsRecommended"
        ]
        .fillna(0)
        .astype(int)
        .eq(1)
    ]
    .copy()
)

capped_recommendation = (
    candidate_performance[
        candidate_performance[
            "AnalysisTrack"
        ]
        .astype(str)
        .str.contains(
            "Capped",
            case=False,
            na=False
        )
        &
        candidate_performance[
            "IsRecommended"
        ]
        .fillna(0)
        .astype(int)
        .eq(1)
    ]
    .copy()
)

st.markdown(
    "#### Recommended Models by Analytical Track"
)

if original_recommendation.empty:

    st.warning(
        "No recommended Original-track candidate was found."
    )

else:

    original_candidate = (
        original_recommendation.iloc[0]
    )

    original_col, capped_col = st.columns(2)

    with original_col:

        st.markdown(
            "### Original Track Winner"
        )

        st.metric(
            "Recommended Model",
            str(
                original_candidate[
                    "Model"
                ]
            )
        )

        original_metric_col1, original_metric_col2 = (
            st.columns(2)
        )

        original_metric_col1.metric(
            "RMSE",
            f"{float(original_candidate['RMSE']):.6f}"
        )

        original_metric_col2.metric(
            "MAE",
            f"{float(original_candidate['MAE']):.6f}"
        )

        st.success(
            "Production Governance Recommendation. "
            "This is the candidate considered for production "
            "promotion."
        )

    with capped_col:

        st.markdown(
            "### Capped Track Winner"
        )

        if capped_recommendation.empty:

            st.warning(
                "No recommended Capped-track candidate was found."
            )

        else:

            capped_candidate = (
                capped_recommendation.iloc[0]
            )

            st.metric(
                "Recommended Model",
                str(
                    capped_candidate[
                        "Model"
                    ]
                )
            )

            capped_metric_col1, capped_metric_col2 = (
                st.columns(2)
            )

            capped_metric_col1.metric(
                "RMSE",
                f"{float(capped_candidate['RMSE']):.6f}"
            )

            capped_metric_col2.metric(
                "MAE",
                f"{float(capped_candidate['MAE']):.6f}"
            )

            st.info(
                "Sensitivity Analysis Recommendation. "
                "This result provides supplementary analytical "
                "evidence and is not directly promoted."
            )

st.markdown(
    "#### Evaluation Metadata"
)

metadata_col1, metadata_col2 = (
    st.columns(2)
)

metadata_col1.text_input(
    "Candidate Upload Batch",
    value=str(
        candidate[
            "UploadBatchID"
        ]
    ),
    disabled=True
)

metadata_col2.text_input(
    "Production Updated",
    value="No",
    disabled=True
)

st.info(
    "The candidate dataset and model-performance results "
    "remain in staging. Production data and production model "
    "status will change only after the authorized governance "
    "decision is executed."
)
# ============================================================
# SECTION 1: APPROVED DATASET SUMMARY
# ============================================================

st.divider()

st.subheader(
    "1.Research Baseline and Candidate Evaluation"
)
st.caption(
    "This section separates the original research findings "
    "from the latest candidate evaluation results."
)
st.info(
    """
### Research Baseline (Static)

The following results represent the original four-project
research dataset used during system development and thesis
evaluation.

These findings remain unchanged even when new approved
datasets are submitted.

Original Track Winner
• Model: Naive Persistence
• RMSE: 7.616301
• MAE: 0.570670

Capped Track Winner
• Model: Random Forest
• RMSE: 0.206468
• MAE: 0.134001

Research Dataset
• Projects: 4
• Test Rows: 756
"""
)

st.info(
    """
Why Two Analytical Tracks?

The Original Track preserves achievement ratios exactly as
reported in project monitoring data. This track is used
for model governance decisions and production promotion.

The Capped Track limits extreme achievement-ratio values
and is used for sensitivity analysis and comparison. It
helps determine whether unusually large values influence
model performance.

Both tracks are displayed during lifecycle review so that
reviewers can compare results. Production promotion
decisions remain focused on the Original Track.
"""
)

try:

    approved_summary = (
        build_approved_dataset_summary()
    )

except Exception as error:

    st.error(
        "The latest approved dataset could not be prepared "
        "for lifecycle review."
    )

    st.exception(
        error
    )

    st.stop()


if approved_summary is None:

    st.warning(
        "No approved ITT dataset is currently available."
    )

    st.info(
        "Upload an ITT, complete data review, and approve "
        "the batch before starting lifecycle evaluation."
    )

    st.stop()


summary_col1, summary_col2, summary_col3, summary_col4 = (
    st.columns(4)
)

# --------------------------------------------------
# OLD APPROVED DATASET SUMMARY REMOVED
# This information is replaced by the
# Research Baseline and Candidate Evaluation sections.
# --------------------------------------------------

dataset_ready = True



st.success(
    "Research Baseline loaded. Candidate evaluation results "
    "are displayed below and will be used for lifecycle review."
)



project_summary = (
    approved_summary[
        "DashboardData"
    ]
    .groupby(
        "Project",
        dropna=False,
    )
    .agg(
        Indicators=(
            "IndicatorID",
            "nunique",
        ),
        DashboardRecords=(
            "IndicatorID",
            "size",
        ),
    )
    .reset_index()
    .sort_values(
        "Project"
    )
)

with st.expander(
    "View approved portfolio composition",
    expanded=False,
):

    st.dataframe(
        project_summary,
        hide_index=True,
        use_container_width=True,
    )

# ============================================================
# SECTION 2: MODEL TRAINING SUMMARY
# ============================================================

st.divider()

st.subheader(
    "2.Candidate Model Training Summary"
)

st.caption(
"The candidate dataset is evaluated in staging before "
"any production data or model is changed. Performance "
"is measured using actual test records, and the candidate "
"recommendation is selected using RMSE and MAE."
)

conn = sqlite3.connect(
    DB_FILE
)

try:

    model_performance = pd.read_sql_query(
        """
        SELECT *
        FROM model_performance_staging
        """,
        conn
    )

finally:

    conn.close()

if model_performance.empty:

    st.warning(
        "No model performance results available."
    )

else:
    total_models = (
        model_performance[
            "Model"
        ].nunique()
    )

    max_test_rows = int(
        pd.to_numeric(
            model_performance["TestRows"],
            errors="coerce"
    ).max()
)

    evaluation_date = str(
        model_performance[
            "EvaluationDate"
        ].max()
    )

    recommended_models = int(
        model_performance[
            "IsRecommended"
        ]
        .fillna(False)
        .astype(bool)
        .sum()
)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
       "Forecasting Models",
       model_performance[
        "Model"
    ].nunique()
)

    col2.metric(
        "Test Records",
        f"{max_test_rows:,}"
    )

    col3.metric(
        "Evaluation Date",
        evaluation_date
    )

    col4.metric(
    "Analytical Tracks",
    model_performance[
        "AnalysisTrack"
    ].nunique()
)

    display_columns = [
        "AnalysisTrack",
        "Model",
        "MAE",
        "RMSE",
        "MAE_Rank",
        "RMSE_Rank"
    ]

    available_columns = [
        c
        for c in display_columns
        if c in model_performance.columns
    ]

    st.dataframe(
        model_performance[
            available_columns
        ].sort_values(
            [
                "AnalysisTrack",
                "RMSE_Rank"
            ]
        ),
        use_container_width=True,
        hide_index=True
    )
    
    st.subheader(
        "Best Model by Analysis Track"
    )

    best_models = (
        model_performance
        .sort_values(
            [
                "AnalysisTrack",
                "RMSE"
            ]
        )
        .groupby(
            "AnalysisTrack",
            as_index=False
        )
        .first()
    )

    original_result = (
        best_models[
            best_models[
                "AnalysisTrack"
            ]
            .astype(str)
            .str.contains(
                "Original",
                case=False,
                na=False
            )
        ]
    )

    capped_result = (
        best_models[
            best_models[
                "AnalysisTrack"
            ]
            .astype(str)
            .str.contains(
                "Capped",
                case=False,
                na=False
            )
        ]
    )

    track_col1, track_col2 = st.columns(2)

    with track_col1:

        if not original_result.empty:

            record = original_result.iloc[0]

            st.success(
                "Production Governance Recommendation"
            )

            st.metric(
                "Original Track Winner",
                str(record["Model"])
            )

            metric_col1, metric_col2 = st.columns(2)

            metric_col1.metric(
                "RMSE",
                f"{float(record['RMSE']):.6f}"
            )

            metric_col2.metric(
                "MAE",
                f"{float(record['MAE']):.6f}"
            )

            st.caption(
                "The Original Track recommendation is used for "
                "production promotion decisions."
            )

    with track_col2:

        if not capped_result.empty:

            record = capped_result.iloc[0]

            st.info(
                "Sensitivity Analysis Recommendation"
            )

            st.metric(
                "Capped Track Winner",
                str(record["Model"])
            )

            metric_col1, metric_col2 = st.columns(2)

            metric_col1.metric(
                "RMSE",
                f"{float(record['RMSE']):.6f}"
            )

            metric_col2.metric(
                "MAE",
                f"{float(record['MAE']):.6f}"
            )

            st.caption(
                "The Capped Track recommendation supports "
                "comparison and validation but is not directly "
                "promoted to production."
            )

    st.markdown(
        """
### Model Selection Process

The approved portfolio dataset is used to retrain:

- Naive Persistence
- Linear Regression
- Random Forest
- XGBoost

The recommended model is selected using:

1. Lowest RMSE
2. Lowest MAE
"""
    )
# ============================================================
# SECTION 3: RECOMMENDED PRODUCTION MODEL
# ============================================================

st.divider()

st.subheader(
    "3.Production Governance Recommendation"
)

st.caption(
    "Following candidate evaluation, the Original Track"
    "recommendation is presented for governance review and"
    "potential production promotion."
)

conn = sqlite3.connect(
    DB_FILE
)

try:

    recommendations = (
        model_performance[
            model_performance[
                "IsRecommended"
            ]
            .fillna(False)
            .astype(bool)
        ]
        .copy()
    )

finally:

    conn.close()
    


if recommendations.empty:

    st.warning(
        "No model recommendation is available."
    )

else:

    original_recommendation = (
        recommendations[
            recommendations[
                "AnalysisTrack"
            ]
            .astype(str)
            .str.contains(
                "Original",
                case=False,
                na=False
            )
        ]
    )

    if original_recommendation.empty:

        st.warning(
            "No Original-track recommendation was found."
        )

    else:

        recommended = (
            original_recommendation
            .iloc[0]
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Candidate Recommendation",
            str(
                recommended["Model"]
            )
        )

        col2.metric(
            "Track",
            str(
                recommended[
                    "AnalysisTrack"
                ]
            )
        )

        col3.metric(
            "RMSE",
            round(
                float(
                    recommended[
                        "RMSE"
                    ]
                ),
                4
            )
        )

        col4.metric(
            "MAE",
            round(
                float(
                    recommended[
                        "MAE"
                    ]
                ),
                4
            )
        )

        st.success(
            f"""
Candidate Recommendation for Governance Review

{recommended['Model']}

This recommendation was generated from the
latest candidate evaluation run in staging.

No production promotion has occurred yet.
A human reviewer must approve or reject the
candidate before production is updated.
"""
        )

        st.markdown(
            f"""
### Selection Rule

{recommended['SelectionRule']}
"""
        )

        st.dataframe(
            original_recommendation,
            hide_index=True,
            use_container_width=True
        )

# ============================================================
# SECTION 4: CAPPED TRACK SUMMARY
# ============================================================

st.divider()

st.subheader(
    "4. Capped Track Summary"
)

st.caption(
    "The capped analytical track is retained for sensitivity "
    "analysis and comparison purposes. It is not used for "
    "production deployment decisions."
)

capped_recommendation = (
    recommendations[
        recommendations[
            "AnalysisTrack"
        ]
        .astype(str)
        .str.contains(
            "Capped",
            case=False,
            na=False
        )
    ]
)

if capped_recommendation.empty:

    st.warning(
        "No capped-track recommendation is available."
    )

else:

    capped_model = (
        capped_recommendation
        .iloc[0]
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Best Capped Model",
        str(
            capped_model["Model"]
        )
    )

    col2.metric(
        "RMSE",
        round(
            float(
                capped_model["RMSE"]
            ),
            4
        )
    )

    col3.metric(
        "MAE",
        round(
            float(
                capped_model["MAE"]
            ),
            4
        )
    )

    st.info(
        f"""
Sensitivity Analysis Winner:

{capped_model['Model']}

This model represents the strongest performer
within the capped achievement-ratio analysis.
It is maintained for comparison and validation
purposes and is not promoted to production.
"""
    )

# ============================================================
# SECTION 5: GOVERNANCE DECISION
# ============================================================

st.divider()

st.subheader(
    "5. Governance Decision"
)

st.caption(
    "Human reviewers validate the recommendation before "
    "a production deployment decision is made."
)

review_col1, review_col2, review_col3, review_col4 = (
    st.columns(4)
)

review_col1.metric(
    "Dataset Approved",
    "Yes"
)

review_col2.metric(
    "Models Trained",
    "Yes"
)

review_col3.metric(
    "Recommendation Generated",
    "Yes"
)

review_col4.metric(
    "Ready for Review",
    (
        "Yes"
        if dataset_ready
        else "No"
    )
)

st.markdown(
    "### Current Governance Position"
)

st.success(
    f"""
Recommended Production Model:

{recommended['Model']}

The latest approved portfolio dataset has been
processed successfully.

All available forecasting models were evaluated.

The recommended model achieved the strongest
performance according to the model selection rule.

A reviewer may now accept or reject this
recommendation.
"""
)

reviewer_name = st.text_input(
    "Reviewer Name",
    placeholder="Enter reviewer name"
)

decision_reason = st.text_area(
    "Decision Rationale",
    placeholder=(
        "Provide the governance rationale for "
        "promotion or rejection."
    ),
    height=120
)

decision_choice = st.radio(
    "Lifecycle Decision",
    [
        "No Action",
        "Promote Candidate",
        "Reject Candidate"
    ],
    horizontal=True
)

if decision_choice == "Promote Model":

    st.success(
        f"""
Governance Decision:

PROMOTE CANDIDATE

Recommended Model:
{recommended['Model']}

Status:
Ready for deployment approval.
"""
    )

elif decision_choice == "Reject Candidate":

    st.warning(
        f"""
Governance Decision:

REJECT CANDIDATE

Recommended Model:
{recommended['Model']}

Status:
Retain the current production model.
"""
    )

else:

    st.info(
        "Select a governance decision after reviewing "
        "the approved dataset and model evaluation results."
    )
    # ============================================================
# SECTION 6: DECISION IMPACT PREVIEW
# ============================================================

st.divider()

st.subheader(
    "6. Decision Impact Preview"
)

st.caption(
    "Review the operational impact before any lifecycle "
    "decision is executed."
)

if decision_choice == "Promote Model":

    st.success(
        f"""
### Promotion Impact

Approved Dataset:
{approved_summary['UploadBatchID']}

Recommended Model:
{recommended['Model']}

Expected Actions:

→ Deploy recommended model

→ Update production model registry

→ Activate latest approved dataset

→ Refresh portfolio dashboards

→ Enable future forecasting using the promoted model
"""
    )

elif decision_choice == "Reject Candidate":

    st.warning(
        f"""
### Candidate Rejection Impact

Approved Dataset:
{approved_summary['UploadBatchID']}

Recommended Model:
{recommended['Model']}

Expected Actions:

→ Keep current production model

→ Record governance decision

→ Retain approved dataset for future review

→ Maintain current forecasting workflow

→ No dashboard deployment changes
"""
    )

else:

    st.info(
        """
Select a lifecycle decision to preview its impact.

No production changes will occur until a governance
decision is approved.
"""
    )
    # ============================================================
# SECTION 7: EXECUTION AUTHORIZATION
# ============================================================

st.divider()

st.subheader(
    "7. Execution Authorization"
)

st.caption(
    "Production lifecycle actions require reviewer "
    "authorization before execution."
)

authorization_confirmed = st.checkbox(
    "I understand that this action may affect production monitoring data and forecasting outputs."
)

authorization_text = st.text_input(
    "Confirmation Statement",
    placeholder="Type: APPROVE EXECUTION"
)

execution_ready = (
    reviewer_name.strip() != ""
    and decision_reason.strip() != ""
    and authorization_confirmed
    and authorization_text.strip() == "APPROVE EXECUTION"
    and decision_choice != "No Action"
)

st.markdown(
    "### Authorization Status"
)

if execution_ready:

    st.success(
        """
Authorization Complete

The lifecycle decision has been reviewed and is
ready for execution.
"""
    )

else:

    st.warning(
        """
Execution requirements are not yet complete.

Required:

• Reviewer Name

• Decision Rationale

• Lifecycle Decision Selection

• Authorization Checkbox

• Confirmation Statement
"""
    )

execute_button = st.button(
    "Execute Lifecycle Decision",
    type="primary",
    disabled=not execution_ready
)
if execute_button:

    try:

        execution_result = (
            execute_governance_decision(
                action=decision_choice,
                reviewer_name=reviewer_name,
                decision_reason=decision_reason,
                approved_summary=approved_summary,
                recommended=recommended,
            )
        )

        st.success(
            "The lifecycle decision was executed successfully."
        )

        st.json(
            execution_result
        )

        st.cache_data.clear()

    except Exception as error:

        if (
            "already the current Original-track Production model"
            in str(error)
        ):

            st.info(
                """
No Promotion Required

The recommended model is already the active
production model.

Current Production Model:
Naive Persistence v2.0

A new candidate version must be generated through
retraining before another promotion can occur.
"""
            )

        else:

            st.error(
                "The lifecycle decision could not be completed. "
                "All database changes were rolled back."
            )

            st.exception(
                error
            )
    

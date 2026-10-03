
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
# SECTION 1: APPROVED DATASET SUMMARY
# ============================================================

st.divider()

st.subheader(
    "1. Approved Dataset Summary"
)

st.caption(
    "This section links the Data Review & Approval workflow "
    "to model retraining and lifecycle governance."
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

summary_col1.metric(
    "Projects",
    f"{approved_summary['ProjectCount']:,}",
)

summary_col2.metric(
    "Indicators",
    f"{approved_summary['IndicatorCount']:,}",
)

summary_col3.metric(
    "Longitudinal Records",
    f"{approved_summary['LongitudinalRecordCount']:,}",
)

summary_col4.metric(
    "Approval Status",
    approved_summary[
        "Status"
    ],
)


detail_col1, detail_col2, detail_col3, detail_col4 = (
    st.columns(4)
)

detail_col1.metric(
    "Uploaded ITT Rows",
    f"{approved_summary['ITTRecordCount']:,}",
)

detail_col2.metric(
    "Dashboard Records",
    f"{approved_summary['DashboardRecordCount']:,}",
)

detail_col3.metric(
    "Duplicate Keys",
    f"{approved_summary['DuplicateKeys']:,}",
)

dataset_ready = (
    approved_summary[
        "DuplicateKeys"
    ]
    == 0
)

detail_col4.metric(
    "Dataset Readiness",
    (
        "Ready"
        if dataset_ready
        else "Review Required"
    ),
)


st.markdown(
    f"""
**Upload batch:** `{approved_summary['UploadBatchID']}`

**Source file:** `{approved_summary['FileName']}`

**Approved by:** {
    approved_summary['ApprovedBy']
    if pd.notna(
        approved_summary['ApprovedBy']
    )
    else 'Not recorded'
}

**Approved UTC:** {
    approved_summary['ApprovedTimestampUTC']
    if pd.notna(
        approved_summary['ApprovedTimestampUTC']
    )
    else 'Not recorded'
}
"""
)


if dataset_ready:

    st.success(
        "The approved dataset has been reconstructed, "
        "transformed, and validated for model retraining."
    )

else:

    st.error(
        "The approved dataset contains duplicate "
        "Project–Indicator–Year–Quarter keys. "
        "Retraining must not proceed until they are resolved."
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
    "2. Model Training Summary"
)

st.caption(
"The latest approved portfolio dataset is automatically "
"used to retrain all available forecasting models. "
"Performance is evaluated using actual test records and "
"the recommended model is selected based on RMSE and MAE."
)

conn = sqlite3.connect(
    DB_FILE
)

try:

    model_performance = pd.read_sql_query(
        """
        SELECT *
        FROM model_performance
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
        "Models Evaluated",
        total_models
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
        "Recommended Models",
        recommended_models
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
    st.markdown(
        "### Best Model by Analysis Track"
    )

    best_models = (
        model_performance
        .sort_values(
            [
                "AnalysisTrack",
                "RMSE_Rank"
            ]
        )
        .groupby(
            "AnalysisTrack",
            as_index=False
        )
        .first()
    )

    st.dataframe(
        best_models[
            [
                "AnalysisTrack",
                "Model",
                "RMSE",
                "MAE",
                "GovernanceRank"
            ]
        ],
        hide_index=True,
        use_container_width=True
    )
    st.markdown(
        "### Best Model by Analysis Track"
    )

    best_models = (
        model_performance
        .sort_values(
            [
                "AnalysisTrack",
                "RMSE_Rank"
            ]
        )
        .groupby(
            "AnalysisTrack",
            as_index=False
        )
        .first()
    )

    st.dataframe(
        best_models[
            [
                "AnalysisTrack",
                "Model",
                "RMSE",
                "MAE",
                "GovernanceRank"
            ]
        ],
        hide_index=True,
        use_container_width=True
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
    "3. Recommended Production Model"
)

st.caption(
    "Following retraining, the system recommends the best "
    "performing model using the approved portfolio dataset."
)

conn = sqlite3.connect(
    DB_FILE
)

try:

    recommendations = pd.read_sql_query(
        """
        SELECT *
        FROM model_recommendation
        """,
        conn
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
            "Recommended Model",
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
Recommended Production Model:

{recommended['Model']}

The recommendation was generated from the
latest retraining cycle using the approved
portfolio dataset.
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
        "Promote Model",
        "Decline Recommendation"
    ],
    horizontal=True
)

if decision_choice == "Promote Model":

    st.success(
        f"""
Governance Decision:

PROMOTE

Recommended Model:
{recommended['Model']}

Status:
Ready for deployment approval.
"""
    )

elif decision_choice == "Decline Recommendation":

    st.warning(
        f"""
Governance Decision:

DECLINE

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

elif decision_choice == "Decline Recommendation":

    st.warning(
        f"""
### Decline Impact

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

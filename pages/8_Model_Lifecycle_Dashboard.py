
import sqlite3

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
# PLACEHOLDER FOR NEXT SECTIONS
# ============================================================

st.divider()

st.subheader(
    "2. Model Training Summary"
)

st.info(
    "The next implementation step will compare the four "
    "available models using the approved portfolio dataset "
    "and display training records, test records, MAE, RMSE, "
    "and ranking."
)

st.divider()

st.subheader(
    "3. Recommended Production Model"
)

st.info(
    "The recommended Original-track model will be selected "
    "from the retraining results using lowest RMSE and then "
    "lowest MAE."
)

st.divider()

st.subheader(
    "4. Capped Track Summary"
)

st.info(
    "The Capped track will remain a read-only sensitivity "
    "analysis summary. Production promotion will apply only "
    "to the Original track."
)

st.divider()

st.subheader(
    "5. Governance Decision"
)

st.info(
    "Promote and Decline controls will be added after the "
    "training and recommendation sections are validated."
)

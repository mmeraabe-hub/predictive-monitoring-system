
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Automation Monitoring",
    page_icon="⚙️",
    layout="wide"
)


# ============================================================
# PROFESSIONAL PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>
    .page-title {
        color: #1F4E78;
        font-size: 2.25rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .page-subtitle {
        color: #64748B;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .section-caption {
        color: #64748B;
        font-size: 0.93rem;
        margin-top: -0.4rem;
        margin-bottom: 1rem;
    }

    .status-success {
        background-color: #EFF8F0;
        border-left: 6px solid #2E7D32;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .status-warning {
        background-color: #FFF8E1;
        border-left: 6px solid #F9A825;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .status-error {
        background-color: #FDECEC;
        border-left: 6px solid #C62828;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .governance-card {
        background-color: #F6F9FC;
        border-left: 6px solid #1F4E78;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .model-card-original {
        background-color: #EEF5FB;
        border: 1px solid #C9DCEC;
        border-radius: 8px;
        padding: 1rem;
        min-height: 118px;
    }

    .model-card-capped {
        background-color: #EFF8F0;
        border: 1px solid #C8E6C9;
        border-radius: 8px;
        padding: 1rem;
        min-height: 118px;
    }

    .detail-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }

    .small-label {
        color: #64748B;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03rem;
    }

    .large-value {
        color: #1F2937;
        font-size: 1.1rem;
        font-weight: 700;
        margin-top: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="page-title">
        ⚙️ Automation Monitoring Dashboard
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="page-subtitle">
        Monitor ETL, UPSERT, retraining, governance, and model
        recommendation activity through a unified operational view.
    </div>
    """,
    unsafe_allow_html=True
)

st.info(
    """
    This dashboard is read-only.

    It displays automation and governance history but does not
    execute ETL, retraining, model promotion, or database updates.
    """
)

# ============================================================
# DATABASE PATH
# ============================================================

DB_FILE = (
    Path(__file__).resolve().parents[1]
    / "predictive_monitoring.db"
)


# ============================================================
# REQUIRED AND OPTIONAL COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "RunID",
    "TriggerSource",
    "RunStartUTC",
    "RunEndUTC",
    "Status"
]


OPTIONAL_COLUMNS = [
    "UploadBatchID",
    "FileName",
    "InputRows",
    "TransformedRows",
    "RowsInserted",
    "RowsUpdated",
    "RowsUnchanged",
    "ErrorMessage",
    "DryRun",
    "CreatedDateUTC",
    "RetrainingStatus",
    "GovernanceStatus",
    "RecommendedOriginalModel",
    "RecommendedCappedModel",
    "AutomationType"
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_value(
    value,
    fallback="Not available"
):

    if value is None:

        return fallback

    try:

        if pd.isna(
            value
        ):

            return fallback

    except (TypeError, ValueError):

        pass

    value_text = str(
        value
    ).strip()

    if value_text.lower() in [
        "",
        "none",
        "nan",
        "nat"
    ]:

        return fallback

    return value_text


def clean_integer(
    value,
    fallback=0
):

    try:

        if pd.isna(
            value
        ):

            return fallback

        return int(
            float(
                value
            )
        )

    except (
        TypeError,
        ValueError
    ):

        return fallback


def format_datetime(
    value
):

    if value is None or pd.isna(
        value
    ):

        return "Not available"

    parsed_value = pd.to_datetime(
        value,
        errors="coerce",
        utc=True
    )

    if pd.isna(
        parsed_value
    ):

        return clean_value(
            value
        )

    return parsed_value.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def status_icon(
    status
):

    normalized_status = clean_value(
        status,
        fallback="Unknown"
    ).strip().lower()

    if normalized_status == "completed":

        return "✅"

    if normalized_status in [
        "failed",
        "error"
    ]:

        return "❌"

    if normalized_status in [
        "running",
        "in progress",
        "pending"
    ]:

        return "🟡"

    return "ℹ️"


def status_style_class(
    status
):

    normalized_status = clean_value(
        status,
        fallback="Unknown"
    ).strip().lower()

    if normalized_status == "completed":

        return "status-success"

    if normalized_status in [
        "failed",
        "error"
    ]:

        return "status-error"

    return "status-warning"


def add_missing_optional_columns(
    dataframe
):

    prepared_dataframe = dataframe.copy()

    for column in OPTIONAL_COLUMNS:

        if column not in prepared_dataframe.columns:

            prepared_dataframe[
                column
            ] = None

    return prepared_dataframe


# ============================================================
# DATA LOADING
# ============================================================
@st.cache_data(ttl=60)
def load_automation_history(database_path):

    database_path = Path(database_path)

    if not database_path.exists():
        raise FileNotFoundError(
            f"Automation database not found: {database_path}"
        )

    with sqlite3.connect(str(database_path)) as connection:

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        table_exists = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'automation_run_history'
            """
        ).fetchone()[0]

        if not table_exists:
            raise RuntimeError(
                "The automation_run_history table does not exist."
            )

        history_data = pd.read_sql_query(
            """
            SELECT *
            FROM automation_run_history
            ORDER BY RunID DESC
            """,
            connection
        )

    if str(integrity).lower() != "ok":
        raise RuntimeError(
            f"SQLite integrity validation failed: {integrity}"
        )

    return history_data


@st.cache_data(ttl=60)
def load_lifecycle_activity():

    with sqlite3.connect(str(DB_FILE)) as connection:

        table_exists = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'model_lifecycle_decision_log'
            """
        ).fetchone()[0]

        if not table_exists:
            return pd.DataFrame()

        lifecycle_data = pd.read_sql_query(
            """
            SELECT *
            FROM model_lifecycle_decision_log
            ORDER BY rowid DESC
            """,
            connection
        )

    return lifecycle_data




try:

    history = load_automation_history(
        str(
            DB_FILE
        )
    )
    lifecycle_activity = (
        load_lifecycle_activity()
    )


except Exception as error:

    st.error(
        "Automation history could not be loaded."
    )

    st.exception(
        error
    )

    st.stop()
# ============================================================
# LIFECYCLE AUTOMATION STATUS
# ============================================================

st.subheader(
    "🔄 Lifecycle Automation Status"
)

if lifecycle_activity.empty:

    st.info(
        "No lifecycle activity has been recorded yet."
    )

else:

    latest = lifecycle_activity.iloc[0]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Action",
        str(latest["Action"])
    )

    c2.metric(
        "Projects",
        f"{latest['ProjectsBefore']} → {latest['ProjectsAfter']}"
    )

    c3.metric(
        "Rows",
        f"{latest['DashboardRowsBefore']} → {latest['DashboardRowsAfter']}"
    )

    c4.metric(
        "Status",
        str(latest["TransactionStatus"])
    )

    st.caption(
        f"Decision Timestamp: {latest['DecisionTimestampUTC']} | "
        f"Upload Batch: {latest['UploadBatchID']}"
    )

# ============================================================
# SECTION 2: AUTOMATION RUN HISTORY
# ============================================================
st.divider()

st.subheader(
    "2. Automation Run History"
)

st.caption(
    "Lifecycle promotion history and governance activity."
)

if lifecycle_activity.empty:

    st.info(
        "No lifecycle history found."
    )

else:

    display_columns = [
        "DecisionID",
        "DecisionTimestampUTC",
        "Action",
        "UploadBatchID",
        "ProjectsBefore",
        "ProjectsAfter",
        "DashboardRowsBefore",
        "DashboardRowsAfter",
        "TransactionStatus"
    ]

    st.dataframe(
        lifecycle_activity[
            display_columns
        ],
        hide_index=True,
        width="stretch"
    )
# ============================================================
# SECTION 3: RUN DETAILS
# ============================================================

st.divider()

st.subheader(
    "3. Run Details"
)

st.caption(
    "Select a lifecycle decision to inspect."
)

if lifecycle_activity.empty:

    st.info(
        "No lifecycle activity found."
    )

else:

    selected_id = st.selectbox(
        "Select Decision ID",
        lifecycle_activity["DecisionID"].tolist()
    )

    selected_record = lifecycle_activity[
        lifecycle_activity["DecisionID"] == selected_id
    ].iloc[0]

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown(
            "### Lifecycle Information"
        )

        st.info(
            f"""
Decision ID: {selected_record['DecisionID']}

Action: {selected_record['Action']}

Timestamp: {selected_record['DecisionTimestampUTC']}

Upload Batch: {selected_record['UploadBatchID']}
"""
        )

    with col2:

        st.markdown(
            "### Production Change"
        )

        st.info(
            f"""
Production Before:
{selected_record['ProductionModelBefore']} {selected_record['ProductionVersionBefore']}

Production After:
{selected_record['ProductionModelAfter']} {selected_record['ProductionVersionAfter']}

Status:
{selected_record['TransactionStatus']}
"""
        )

    with col3:

        st.markdown(
            "### Impact"
        )

        st.info(
            f"""
Projects:
{selected_record['ProjectsBefore']} → {selected_record['ProjectsAfter']}

Rows:
{selected_record['DashboardRowsBefore']} → {selected_record['DashboardRowsAfter']}

Recommended Model:
{selected_record['RecommendedModel']}
"""
        )
try:

    with sqlite3.connect(
        str(DB_FILE)
    ) as conn:

        registry_data = pd.read_sql_query(
            """
            SELECT *
            FROM model_registry
            """,
            conn
        )

except Exception:

    registry_data = pd.DataFrame()
     
# ============================================================
# CHAMPION MODELS 
# ============================================================


st.divider()

st.subheader(
    "🏆 Champion Models"
)

st.caption(
    "Current production champions for Original and Capped datasets."
)

champion_col1, champion_col2 = st.columns(2)

with champion_col1:

    st.markdown(
        "### Original Dataset Champion"
    )

    original_champion = registry_data[
        (registry_data["DatasetType"] == "Original")
        &
        (registry_data["Status"] == "Production")
    ]

    if original_champion.empty:

        st.warning(
            "No Production champion found."
        )

    else:

        champion = original_champion.iloc[0]

        st.success(
            f"""
Model: {champion['Model']}

Version: {champion['Version']}

MAE: {champion['MAE']:.4f}

RMSE: {champion['RMSE']:.4f}
"""
        )


with champion_col2:

    st.markdown(
        "### Capped Dataset Champion"
    )

    capped_champion = registry_data[
        (registry_data["DatasetType"] == "Capped")
        &
        (registry_data["Status"] == "Production")
    ]

    if capped_champion.empty:

        st.warning(
            "No Production champion found."
        )

    else:

        champion = capped_champion.iloc[0]

        st.success(
            f"""
Model: {champion['Model']}

Version: {champion['Version']}

MAE: {champion['MAE']:.4f}

RMSE: {champion['RMSE']:.4f}
"""
        )



# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Read-only automation monitoring view. "
    "This page does not execute or modify pipeline records."
)

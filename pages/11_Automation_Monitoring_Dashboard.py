
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

@st.cache_data(
    ttl=60
)
def load_automation_history(
    database_path
):

    database_path = Path(
        database_path
    )

    if not database_path.exists():

        raise FileNotFoundError(
            "Automation database not found: "
            f"{database_path}"
        )

    with sqlite3.connect(
        str(
            database_path
        )
    ) as connection:

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
                "The automation_run_history table "
                "does not exist."
            )

        history_data = pd.read_sql_query(
            """
            SELECT *
            FROM automation_run_history
            ORDER BY RunID DESC
            """,
            connection
        )

    if str(
        integrity
    ).lower() != "ok":

        raise RuntimeError(
            "SQLite integrity validation failed: "
            f"{integrity}"
        )

    return history_data


try:

    history = load_automation_history(
        str(
            DB_FILE
        )
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
# DATA VALIDATION
# ============================================================

missing_required_columns = [
    column
    for column in REQUIRED_COLUMNS
    if column not in history.columns
]


if missing_required_columns:

    st.error(
        "The automation history table is missing "
        "required columns: "
        + ", ".join(
            missing_required_columns
        )
    )

    st.stop()


history = add_missing_optional_columns(
    history
)


if history.empty:

    st.warning(
        "No automation run-history records are available."
    )

    st.stop()


# Normalize selected fields.
history[
    "RunID"
] = pd.to_numeric(
    history[
        "RunID"
    ],
    errors="coerce"
)


for numeric_column in [
    "InputRows",
    "TransformedRows",
    "RowsInserted",
    "RowsUpdated",
    "RowsUnchanged",
    "DryRun"
]:

    history[
        numeric_column
    ] = pd.to_numeric(
        history[
            numeric_column
        ],
        errors="coerce"
    )


history[
    "_RunStartParsed"
] = pd.to_datetime(
    history[
        "RunStartUTC"
    ],
    errors="coerce",
    utc=True
)


history[
    "_RunEndParsed"
] = pd.to_datetime(
    history[
        "RunEndUTC"
    ],
    errors="coerce",
    utc=True
)


history[
    "_DurationSeconds"
] = (
    history[
        "_RunEndParsed"
    ]
    -
    history[
        "_RunStartParsed"
    ]
).dt.total_seconds()


history = history.sort_values(
    [
        "_RunStartParsed",
        "RunID"
    ],
    ascending=[
        False,
        False
    ],
    na_position="last"
).reset_index(
    drop=True
)


# ============================================================
# SECTION 1: AUTOMATION SUMMARY
# ============================================================

st.divider()

st.subheader(
    "1. Automation Summary"
)

st.markdown(
    """
    <div class="section-caption">
        High-level status of recorded operational and governance runs.
    </div>
    """,
    unsafe_allow_html=True
)


total_runs = int(
    len(
        history
    )
)


completed_mask = (
    history[
        "Status"
    ]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.lower()
    .eq(
        "completed"
    )
)


successful_runs = int(
    completed_mask.sum()
)


failed_runs = int(
    total_runs
    -
    successful_runs
)


latest_run = history.iloc[0]


latest_run_status = clean_value(
    latest_run[
        "Status"
    ],
    fallback="Unknown"
)


summary_col1, summary_col2, summary_col3, summary_col4 = (
    st.columns(4)
)


with summary_col1:

    st.metric(
        "Total Runs",
        total_runs,
        help=(
            "All records currently stored in "
            "automation_run_history."
        )
    )


with summary_col2:

    st.metric(
        "Successful Runs",
        successful_runs,
        help=(
            "Runs whose Status is Completed."
        )
    )


with summary_col3:

    st.metric(
        "Runs Requiring Attention",
        failed_runs,
        help=(
            "Runs whose Status is not Completed."
        )
    )


with summary_col4:

    st.metric(
        "Latest Run Status",
        (
            status_icon(
                latest_run_status
            )
            + " "
            + latest_run_status
        )
    )


# ============================================================
# SECTION 2: LATEST AUTOMATION STATUS
# ============================================================

st.divider()

st.subheader(
    "2. Latest Automation Status"
)

st.markdown(
    """
    <div class="section-caption">
        The most recent recorded pipeline execution.
    </div>
    """,
    unsafe_allow_html=True
)


latest_style = status_style_class(
    latest_run_status
)


latest_run_id = clean_integer(
    latest_run[
        "RunID"
    ]
)


latest_trigger = clean_value(
    latest_run[
        "TriggerSource"
    ]
)


latest_start = format_datetime(
    latest_run[
        "RunStartUTC"
    ]
)


latest_end = format_datetime(
    latest_run[
        "RunEndUTC"
    ]
)


latest_duration = latest_run[
    "_DurationSeconds"
]


if pd.isna(
    latest_duration
):

    latest_duration_text = (
        "Not available"
    )

else:

    latest_duration_text = (
        f"{float(latest_duration):,.3f} seconds"
    )


st.markdown(
    f"""
    <div class="{latest_style}">
        <strong style="font-size: 1.15rem;">
            {status_icon(latest_run_status)}
            Latest run: {latest_run_status}
        </strong>
        <br><br>
        <strong>Run ID:</strong>
        {latest_run_id}
        <br>
        <strong>Trigger source:</strong>
        {latest_trigger}
        <br>
        <strong>Started:</strong>
        {latest_start}
        <br>
        <strong>Finished:</strong>
        {latest_end}
        <br>
        <strong>Duration:</strong>
        {latest_duration_text}
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SECTION 3: GOVERNANCE COMMAND CENTER
# ============================================================

st.divider()

st.subheader(
    "3. Governance Command Center"
)

st.markdown(
    """
    <div class="section-caption">
        Latest retraining and governance outcome with current
        recommended models for the Original and Capped tracks.
    </div>
    """,
    unsafe_allow_html=True
)


governance_runs = history[
    history[
        "RecommendedOriginalModel"
    ].notna()
    |
    history[
        "RecommendedCappedModel"
    ].notna()
].copy()


if governance_runs.empty:

    st.info(
        "No recorded governance recommendation "
        "is currently available."
    )

else:

    latest_governance = governance_runs.iloc[0]

    governance_run_id = clean_integer(
        latest_governance[
            "RunID"
        ]
    )

    retraining_status = clean_value(
        latest_governance[
            "RetrainingStatus"
        ]
    )

    governance_status = clean_value(
        latest_governance[
            "GovernanceStatus"
        ]
    )

    automation_type = clean_value(
        latest_governance[
            "AutomationType"
        ]
    )

    governance_col1, governance_col2, governance_col3, governance_col4 = (
        st.columns(4)
    )

    with governance_col1:

        st.metric(
            "Governance Run ID",
            governance_run_id
        )

    with governance_col2:

        st.metric(
            "Retraining Status",
            (
                status_icon(
                    retraining_status
                )
                + " "
                + retraining_status
            )
        )

    with governance_col3:

        st.metric(
            "Governance Status",
            (
                status_icon(
                    governance_status
                )
                + " "
                + governance_status
            )
        )

    with governance_col4:

        st.metric(
            "Automation Type",
            automation_type
        )

    original_recommendation = clean_value(
        latest_governance[
            "RecommendedOriginalModel"
        ]
    )

    capped_recommendation = clean_value(
        latest_governance[
            "RecommendedCappedModel"
        ]
    )

    original_model_col, capped_model_col = (
        st.columns(2)
    )

    with original_model_col:

        st.markdown(
            f"""
            <div class="model-card-original">
                <div class="small-label">
                    Original Dataset Recommendation
                </div>
                <div class="large-value">
                    {original_recommendation}
                </div>
                <br>
                <span style="color: #64748B;">
                    Based on the latest completed
                    retraining and governance record.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

    with capped_model_col:

        st.markdown(
            f"""
            <div class="model-card-capped">
                <div class="small-label">
                    Capped Dataset Recommendation
                </div>
                <div class="large-value">
                    {capped_recommendation}
                </div>
                <br>
                <span style="color: #64748B;">
                    Based on the latest completed
                    retraining and governance record.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# SECTION 4: AUTOMATION RUN HISTORY
# ============================================================

st.divider()

st.subheader(
    "4. Automation Run History"
)

st.markdown(
    """
    <div class="section-caption">
        Unified history of approval, UPSERT, retraining,
        and governance executions.
    </div>
    """,
    unsafe_allow_html=True
)


history_display = history.copy()


history_display[
    "Run Start"
] = history_display[
    "RunStartUTC"
].apply(
    format_datetime
)


history_display[
    "Run End"
] = history_display[
    "RunEndUTC"
].apply(
    format_datetime
)


history_display[
    "Duration (sec)"
] = history_display[
    "_DurationSeconds"
].round(
    3
)


history_display[
    "Run Status"
] = history_display[
    "Status"
].apply(
    lambda value: (
        status_icon(
            value
        )
        + " "
        + clean_value(
            value,
            fallback="Unknown"
        )
    )
)


history_columns = [
    "RunID",
    "TriggerSource",
    "Run Status",
    "AutomationType",
    "RetrainingStatus",
    "GovernanceStatus",
    "Run Start",
    "Duration (sec)"
]


st.dataframe(
    history_display[
        history_columns
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "RunID":
            st.column_config.NumberColumn(
                "Run ID",
                format="%d",
                width="small"
            ),

        "TriggerSource":
            st.column_config.TextColumn(
                "Trigger Source",
                width="medium"
            ),

        "Run Status":
            st.column_config.TextColumn(
                "Status",
                width="small"
            ),

        "AutomationType":
            st.column_config.TextColumn(
                "Automation Type",
                width="medium"
            ),

        "RetrainingStatus":
            st.column_config.TextColumn(
                "Retraining",
                width="small"
            ),

        "GovernanceStatus":
            st.column_config.TextColumn(
                "Governance",
                width="small"
            ),

        "Run Start":
            st.column_config.TextColumn(
                "Run Start",
                width="medium"
            ),

        "Duration (sec)":
            st.column_config.NumberColumn(
                "Duration (sec)",
                format="%.3f",
                width="small"
            )
    }
)


# ============================================================
# SECTION 5: RUN DETAILS
# ============================================================

st.divider()

st.subheader(
    "5. Run Details"
)

st.markdown(
    """
    <div class="section-caption">
        Select a run to inspect its execution, data-change,
        governance, recommendation, and error details.
    </div>
    """,
    unsafe_allow_html=True
)


run_options = [
    int(
        value
    )
    for value in history[
        "RunID"
    ].dropna().tolist()
]


selected_run_id = st.selectbox(
    "Select Run ID",
    options=run_options,
    index=0
)


selected_run = history[
    history[
        "RunID"
    ].eq(
        selected_run_id
    )
].iloc[0]


general_col, execution_col, governance_detail_col = (
    st.columns(3)
)


with general_col:

    st.markdown(
        "### Run Information"
    )

    st.markdown(
        f"""
        <div class="detail-card">
            <strong>Run ID:</strong>
            {selected_run_id}
            <br><br>
            <strong>Trigger source:</strong>
            {clean_value(selected_run['TriggerSource'])}
            <br><br>
            <strong>Status:</strong>
            {status_icon(selected_run['Status'])}
            {clean_value(selected_run['Status'])}
            <br><br>
            <strong>Automation type:</strong>
            {clean_value(selected_run['AutomationType'])}
            <br><br>
            <strong>Dry run:</strong>
            {'Yes' if clean_integer(selected_run['DryRun']) == 1 else 'No'}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="detail-card">
            <strong>Started:</strong>
            {format_datetime(selected_run['RunStartUTC'])}
            <br><br>
            <strong>Finished:</strong>
            {format_datetime(selected_run['RunEndUTC'])}
        </div>
        """,
        unsafe_allow_html=True
    )


with execution_col:

    st.markdown(
        "### Execution Statistics"
    )

    execution_rows = pd.DataFrame(
        {
            "Metric": [
                "Input rows",
                "Transformed rows",
                "Rows inserted",
                "Rows updated",
                "Rows unchanged"
            ],

            "Value": [
                clean_integer(
                    selected_run[
                        "InputRows"
                    ]
                ),

                clean_integer(
                    selected_run[
                        "TransformedRows"
                    ]
                ),

                clean_integer(
                    selected_run[
                        "RowsInserted"
                    ]
                ),

                clean_integer(
                    selected_run[
                        "RowsUpdated"
                    ]
                ),

                clean_integer(
                    selected_run[
                        "RowsUnchanged"
                    ]
                )
            ]
        }
    )

    st.dataframe(
        execution_rows,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Metric":
                st.column_config.TextColumn(
                    "Metric",
                    width="medium"
                ),

            "Value":
                st.column_config.NumberColumn(
                    "Rows",
                    format="%d",
                    width="small"
                )
        }
    )

    st.markdown(
        f"""
        <div class="detail-card">
            <strong>Source file:</strong>
            {clean_value(selected_run['FileName'])}
            <br><br>
            <strong>Upload batch:</strong>
            {clean_value(selected_run['UploadBatchID'])}
        </div>
        """,
        unsafe_allow_html=True
    )


with governance_detail_col:

    st.markdown(
        "### Governance Details"
    )

    st.markdown(
        f"""
        <div class="detail-card">
            <strong>Retraining status:</strong>
            {clean_value(selected_run['RetrainingStatus'])}
            <br><br>
            <strong>Governance status:</strong>
            {clean_value(selected_run['GovernanceStatus'])}
            <br><br>
            <strong>Original recommendation:</strong>
            {clean_value(selected_run['RecommendedOriginalModel'])}
            <br><br>
            <strong>Capped recommendation:</strong>
            {clean_value(selected_run['RecommendedCappedModel'])}
        </div>
        """,
        unsafe_allow_html=True
    )

    error_message = clean_value(
        selected_run[
            "ErrorMessage"
        ],
        fallback="No error recorded"
    )

    if error_message == "No error recorded":

        st.success(
            "No error was recorded for this run."
        )

    else:

        st.error(
            error_message
        )
# ============================================================
# CHAMPION MODELS AND ROLLBACK READINESS
# ============================================================

st.divider()

st.subheader(
    "🏆 Champion Models and Rollback Readiness"
)

st.caption(
    "Current production champions and available rollback candidates."
)

champion_col1, champion_col2 = st.columns(2)

with champion_col1:

    st.markdown(
        "### Original Dataset Champion"
    )

    original_champion = registry[
        (registry["DatasetType"] == "Original")
        &
        (registry["Status"] == "Production")
    ]

    if not original_champion.empty:

        original_champion = original_champion.iloc[0]

        st.success(
            f"""
Model: {original_champion['Model']}

Version: {original_champion['Version']}

MAE: {original_champion['MAE']:.4f}

RMSE: {original_champion['RMSE']:.4f}
"""
        )

with champion_col2:

    st.markdown(
        "### Capped Dataset Champion"
    )

    capped_champion = registry[
        (registry["DatasetType"] == "Capped")
        &
        (registry["Status"] == "Production")
    ]

    if not capped_champion.empty:

        capped_champion = capped_champion.iloc[0]

        st.success(
            f"""
Model: {capped_champion['Model']}

Version: {capped_champion['Version']}

MAE: {capped_champion['MAE']:.4f}

RMSE: {capped_champion['RMSE']:.4f}
"""
        )

st.divider()

rollback_col1, rollback_col2 = st.columns(2)

with rollback_col1:

    st.markdown(
        "### Original Rollback Readiness"
    )

    original_retired = registry[
        (registry["DatasetType"] == "Original")
        &
        (registry["Status"] == "Retired")
    ]

    if original_retired.empty:

        st.warning(
            "No rollback candidate available."
        )

    else:

        candidate = original_retired.iloc[0]

        st.info(
            f"""
Rollback Candidate Found

Model:
{candidate['Model']}

Version:
{candidate['Version']}
"""
        )

with rollback_col2:

    st.markdown(
        "### Capped Rollback Readiness"
    )

    capped_retired = registry[
        (registry["DatasetType"] == "Capped")
        &
        (registry["Status"] == "Retired")
    ]

    if capped_retired.empty:

        st.warning(
            "No rollback candidate available."
        )

    else:

        candidate = capped_retired.iloc[0]

        st.info(
            f"""
Rollback Candidate Found

Model:
{candidate['Model']}

Version:
{candidate['Version']}
"""
        )

st.info(
    """
Champion = Current Production model

Rollback Candidate = A previously Retired model that could
potentially be restored after governance review.

This section is READ ONLY and performs no database updates.
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

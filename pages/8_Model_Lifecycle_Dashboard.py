
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st

from utils.database_utils import DB_FILE


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Model Lifecycle Management",
    page_icon="🔄",
    layout="wide"
)


# ============================================================
# PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>
    .page-title {
        color: #1F4E78;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .page-subtitle {
        color: #64748B;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .recommendation-promote {
        background-color: #EFF8F0;
        border-left: 6px solid #2E7D32;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .recommendation-review {
        background-color: #FFF8E1;
        border-left: 6px solid #F9A825;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .recommendation-decline {
        background-color: #FDECEC;
        border-left: 6px solid #C62828;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .governance-note {
        background-color: #F6F9FC;
        border-left: 6px solid #1F4E78;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 1rem;
    }

    .dataset-heading {
        color: #1F4E78;
        font-size: 1.35rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="page-title">
        Model Lifecycle Management Dashboard
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="page-subtitle">
        Compare current production models with newly retrained
        candidate versions, review governance recommendations,
        and inspect the evidence supporting each recommendation.
    </div>
    """,
    unsafe_allow_html=True
)

st.info(
    """
    This dashboard is currently read-only.

    It displays lifecycle recommendations but does not promote,
    decline, retire, or otherwise modify any model.
    """
)


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data
def load_lifecycle_data():

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        registry = pd.read_sql_query(
            """
            SELECT
                Model,
                DatasetType,
                Version,
                TrainingDate,
                TestRows,
                MAE,
                RMSE,
                Status
            FROM model_registry
            """,
            conn
        )

        performance = pd.read_sql_query(
            """
            SELECT
                AnalysisTrack,
                Model,
                TargetScale,
                TestRows,
                MAE,
                RMSE,
                MAE_Rank,
                RMSE_Rank,
                DatasetType,
                GovernanceRank,
                IsRecommended,
                SelectionRule,
                EvaluationDate
            FROM model_performance
            """,
            conn
        )

        recommendations = pd.read_sql_query(
            """
            SELECT
                AnalysisTrack,
                Model,
                TargetScale,
                TestRows,
                MAE,
                RMSE,
                MAE_Rank,
                RMSE_Rank,
                DatasetType,
                GovernanceRank,
                IsRecommended,
                SelectionRule,
                EvaluationDate
            FROM model_recommendation
            """,
            conn
        )

        drift = pd.read_sql_query(
            """
            SELECT
                EvaluationDate,
                Model,
                DatasetType,
                PreviousRMSE,
                CurrentRMSE,
                DriftPercent,
                DriftFlag,
                PreviousVersion,
                CurrentVersion
            FROM model_drift_history
            """,
            conn
        )

    finally:

        conn.close()

    return (
        registry,
        performance,
        recommendations,
        drift
    )


try:

    (
        registry_data,
        performance_data,
        recommendation_data,
        drift_data
    ) = load_lifecycle_data()

except Exception as error:

    st.error(
        "The model lifecycle data could not be loaded."
    )

    st.exception(error)
    st.stop()


# ============================================================
# BASIC DATA VALIDATION
# ============================================================

if registry_data.empty:

    st.warning(
        "The model registry contains no records."
    )

    st.stop()


required_registry_columns = [
    "Model",
    "DatasetType",
    "Version",
    "TrainingDate",
    "TestRows",
    "MAE",
    "RMSE",
    "Status"
]


missing_registry_columns = [
    column
    for column in required_registry_columns
    if column not in registry_data.columns
]


if missing_registry_columns:

    st.error(
        "Required model-registry columns are missing: "
        + ", ".join(
            missing_registry_columns
        )
    )

    st.stop()


for dataframe in [
    registry_data,
    performance_data,
    recommendation_data,
    drift_data
]:

    for numeric_column in [
        "TestRows",
        "MAE",
        "RMSE",
        "MAE_Rank",
        "RMSE_Rank",
        "GovernanceRank",
        "IsRecommended",
        "PreviousRMSE",
        "CurrentRMSE",
        "DriftPercent"
    ]:

        if numeric_column in dataframe.columns:

            dataframe[numeric_column] = pd.to_numeric(
                dataframe[numeric_column],
                errors="coerce"
            )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def version_number(
    version
):

    version_text = str(
        version
    ).strip().lower()

    version_text = (
        version_text
        .replace(
            "version",
            ""
        )
        .replace(
            "v",
            ""
        )
        .strip()
    )

    try:

        return float(
            version_text
        )

    except ValueError:

        return 0.0


def safe_metric(
    value,
    decimals=4
):

    if pd.isna(value):

        return "Not available"

    return f"{float(value):,.{decimals}f}"


def safe_percent(
    value,
    decimals=2
):

    if pd.isna(value):

        return "Not available"

    return f"{float(value):,.{decimals}f}%"


def latest_version_row(
    data
):

    if data.empty:

        return None

    working_data = data.copy()

    working_data[
        "_VersionNumber"
    ] = working_data[
        "Version"
    ].apply(
        version_number
    )

    working_data = working_data.sort_values(
        [
            "_VersionNumber",
            "TrainingDate"
        ],
        ascending=[
            False,
            False
        ]
    )

    return working_data.iloc[0]


def latest_matching_drift(
    dataset_type,
    model_name,
    candidate_version
):

    matching_drift = drift_data[
        drift_data[
            "DatasetType"
        ].astype(str).eq(
            dataset_type
        )
        &
        drift_data[
            "Model"
        ].astype(str).eq(
            model_name
        )
        &
        drift_data[
            "CurrentVersion"
        ].astype(str).eq(
            candidate_version
        )
    ].copy()

    if matching_drift.empty:

        return None

    matching_drift[
        "_EvaluationDate"
    ] = pd.to_datetime(
        matching_drift[
            "EvaluationDate"
        ],
        errors="coerce"
    )

    matching_drift = matching_drift.sort_values(
        "_EvaluationDate",
        ascending=False
    )

    return matching_drift.iloc[0]


def get_dataset_lifecycle(
    dataset_type
):

    dataset_registry = registry_data[
        registry_data[
            "DatasetType"
        ].astype(str).eq(
            dataset_type
        )
    ].copy()

    production_records = dataset_registry[
        dataset_registry[
            "Status"
        ].astype(str).str.strip().str.lower().eq(
            "production"
        )
    ].copy()

    production_row = latest_version_row(
        production_records
    )

    dataset_recommendation = recommendation_data[
        recommendation_data[
            "DatasetType"
        ].astype(str).eq(
            dataset_type
        )
    ].copy()

    if dataset_recommendation.empty:

        dataset_performance = performance_data[
            performance_data[
                "DatasetType"
            ].astype(str).eq(
                dataset_type
            )
        ].copy()

        dataset_performance = dataset_performance.sort_values(
            [
                "GovernanceRank",
                "RMSE",
                "MAE"
            ]
        )

        if dataset_performance.empty:

            recommendation_row = None
            recommended_model = None

        else:

            recommendation_row = (
                dataset_performance.iloc[0]
            )

            recommended_model = str(
                recommendation_row[
                    "Model"
                ]
            )

    else:

        dataset_recommendation = (
            dataset_recommendation
            .sort_values(
                [
                    "GovernanceRank",
                    "RMSE",
                    "MAE"
                ]
            )
        )

        recommendation_row = (
            dataset_recommendation.iloc[0]
        )

        recommended_model = str(
            recommendation_row[
                "Model"
            ]
        )

    if recommended_model is None:

        candidate_row = None

    else:

        recommended_candidates = dataset_registry[
            dataset_registry[
                "Model"
            ].astype(str).eq(
                recommended_model
            )
            &
            dataset_registry[
                "Status"
            ].astype(str).str.strip().str.lower().eq(
                "candidate"
            )
        ].copy()

        candidate_row = latest_version_row(
            recommended_candidates
        )

    if candidate_row is None:

        drift_row = None

    else:

        drift_row = latest_matching_drift(
            dataset_type=dataset_type,
            model_name=str(
                candidate_row[
                    "Model"
                ]
            ),
            candidate_version=str(
                candidate_row[
                    "Version"
                ]
            )
        )

    return {
        "DatasetType":
            dataset_type,

        "Production":
            production_row,

        "Candidate":
            candidate_row,

        "Recommendation":
            recommendation_row,

        "Drift":
            drift_row
    }


def evaluate_governance(
    lifecycle
):

    production = lifecycle[
        "Production"
    ]

    candidate = lifecycle[
        "Candidate"
    ]

    recommendation = lifecycle[
        "Recommendation"
    ]

    drift = lifecycle[
        "Drift"
    ]

    if (
        production is None
        or candidate is None
        or recommendation is None
    ):

        return {
            "Action": "Review",
            "Icon": "🟡",
            "Label": "Review Before Decision",
            "StyleClass": "recommendation-review",
            "Narrative": (
                "The available lifecycle information is "
                "incomplete. Expert review is required before "
                "any model lifecycle decision."
            ),
            "Evidence": {
                "Candidate is Rank 1":
                    False,
                "RMSE stable or improved":
                    False,
                "MAE stable or improved":
                    False,
                "Drift within 5%":
                    False,
                "Retraining result available":
                    candidate is not None,
                "Test records available":
                    False
            },
            "Confidence": "Low"
        }

    production_rmse = float(
        production[
            "RMSE"
        ]
    )

    candidate_rmse = float(
        candidate[
            "RMSE"
        ]
    )

    production_mae = float(
        production[
            "MAE"
        ]
    )

    candidate_mae = float(
        candidate[
            "MAE"
        ]
    )

    governance_rank = int(
        recommendation[
            "GovernanceRank"
        ]
    )

    test_rows = int(
        recommendation[
            "TestRows"
        ]
    )

    if drift is None:

        drift_percent = np.nan

    else:

        drift_percent = float(
            drift[
                "DriftPercent"
            ]
        )

    rank_pass = (
        governance_rank == 1
    )

    rmse_pass = (
        candidate_rmse
        <= production_rmse
        + 0.0000001
    )

    mae_pass = (
        candidate_mae
        <= production_mae
        + 0.0000001
    )

    drift_pass = (
        pd.notna(
            drift_percent
        )
        and abs(
            drift_percent
        ) <= 5.0
    )

    retraining_pass = (
        candidate is not None
    )

    test_rows_pass = (
        test_rows > 0
    )

    # --------------------------------------------------------
    # Decision rules
    # --------------------------------------------------------

    if (
        rank_pass
        and rmse_pass
        and drift_pass
    ):

        action = "Promote"
        icon = "🟢"
        label = "Recommended: Promote"
        style_class = (
            "recommendation-promote"
        )
        confidence = "High"

        narrative = (
            "The candidate remains the highest-ranked model "
            "and demonstrates stable or improved RMSE "
            "relative to the current production version. "
            "Model drift is within the accepted 5% tolerance."
        )

    elif (
        rank_pass
        and pd.notna(
            drift_percent
        )
        and abs(
            drift_percent
        ) > 5.0
        and abs(
            drift_percent
        ) <= 10.0
    ):

        action = "Review"
        icon = "🟡"
        label = "Review Before Decision"
        style_class = (
            "recommendation-review"
        )
        confidence = "Medium"

        narrative = (
            "The candidate remains the highest-ranked model, "
            "but its performance has changed sufficiently to "
            "require SME or MEL review before promotion."
        )

    else:

        action = "Decline"
        icon = "🔴"
        label = "Recommended: Decline"
        style_class = (
            "recommendation-decline"
        )
        confidence = "High"

        narrative = (
            "The candidate has not met one or more lifecycle "
            "requirements. Its RMSE is worse than the current "
            "production model, its drift exceeds tolerance, "
            "or it is no longer the highest-ranked candidate."
        )

    return {
        "Action":
            action,

        "Icon":
            icon,

        "Label":
            label,

        "StyleClass":
            style_class,

        "Narrative":
            narrative,

        "Confidence":
            confidence,

        "DriftPercent":
            drift_percent,

        "TestRows":
            test_rows,

        "GovernanceRank":
            governance_rank,

        "Evidence": {
            "Candidate is Rank 1":
                rank_pass,

            "RMSE stable or improved":
                rmse_pass,

            "MAE stable or improved":
                mae_pass,

            "Drift within 5%":
                drift_pass,

            "Retraining result available":
                retraining_pass,

            "Test records available":
                test_rows_pass
        }
    }


def evidence_result(
    passed,
    detail=None
):

    if passed:

        if detail is None:

            return "✅ Pass"

        return f"✅ {detail}"

    if detail is None:

        return "❌ Review"

    return f"❌ {detail}"


def model_label(
    row
):

    if row is None:

        return "Not available"

    return (
        str(
            row[
                "Model"
            ]
        )
        + " "
        + str(
            row[
                "Version"
            ]
        )
    )


# ============================================================
# BUILD LIFECYCLE OBJECTS
# ============================================================

original_lifecycle = get_dataset_lifecycle(
    "Original"
)

capped_lifecycle = get_dataset_lifecycle(
    "Capped"
)


original_governance = evaluate_governance(
    original_lifecycle
)

capped_governance = evaluate_governance(
    capped_lifecycle
)


lifecycle_by_dataset = {
    "Original":
        original_lifecycle,

    "Capped":
        capped_lifecycle
}


governance_by_dataset = {
    "Original":
        original_governance,

    "Capped":
        capped_governance
}


# ============================================================
# SECTION 0: GOVERNANCE SUMMARY
# ============================================================

st.divider()

st.subheader(
    "Governance Summary"
)

st.caption(
    "Current production models and recommended candidate "
    "versions for the Original and Capped analysis tracks."
)


summary_rows = []


for dataset_type in [
    "Original",
    "Capped"
]:

    lifecycle = lifecycle_by_dataset[
        dataset_type
    ]

    governance = governance_by_dataset[
        dataset_type
    ]

    summary_rows.append(
        {
            "Dataset":
                dataset_type,

            "Production Model":
                model_label(
                    lifecycle[
                        "Production"
                    ]
                ),

            "Candidate Model":
                model_label(
                    lifecycle[
                        "Candidate"
                    ]
                ),

            "Recommendation":
                (
                    governance[
                        "Icon"
                    ]
                    + " "
                    + governance[
                        "Label"
                    ]
                )
        }
    )


governance_summary = pd.DataFrame(
    summary_rows
)


st.dataframe(
    governance_summary,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Dataset":
            st.column_config.TextColumn(
                "Dataset",
                width="small"
            ),

        "Production Model":
            st.column_config.TextColumn(
                "Current Production",
                width="medium"
            ),

        "Candidate Model":
            st.column_config.TextColumn(
                "Recommended Candidate",
                width="medium"
            ),

        "Recommendation":
            st.column_config.TextColumn(
                "System Recommendation",
                width="medium"
            )
    }
)


# ============================================================
# SECTION 1: SIDE-BY-SIDE MODEL COMPARISON
# ============================================================

st.divider()

st.subheader(
    "Production and Candidate Model Comparison"
)

st.caption(
    "The Original and Capped tracks use different target "
    "scales. Their MAE and RMSE values should be interpreted "
    "within each track rather than compared directly across "
    "the two scales."
)


def comparison_value(
    row,
    column,
    value_type="text"
):

    if row is None:

        return "Not available"

    value = row.get(
        column,
        np.nan
    )

    if value_type == "metric":

        return safe_metric(
            value
        )

    if value_type == "integer":

        if pd.isna(
            value
        ):

            return "Not available"

        return str(
            int(
                value
            )
        )

    return str(
        value
    )


original_production = (
    original_lifecycle[
        "Production"
    ]
)

original_candidate = (
    original_lifecycle[
        "Candidate"
    ]
)

capped_production = (
    capped_lifecycle[
        "Production"
    ]
)

capped_candidate = (
    capped_lifecycle[
        "Candidate"
    ]
)


comparison_table = pd.DataFrame(
    {
        "Metric": [
            "Model",
            "Version",
            "Status",
            "RMSE",
            "MAE",
            "Drift",
            "Governance Rank",
            "Test Records"
        ],

        "Original Production": [
            comparison_value(
                original_production,
                "Model"
            ),
            comparison_value(
                original_production,
                "Version"
            ),
            comparison_value(
                original_production,
                "Status"
            ),
            comparison_value(
                original_production,
                "RMSE",
                "metric"
            ),
            comparison_value(
                original_production,
                "MAE",
                "metric"
            ),
            "Not applicable",
            "1",
            comparison_value(
                original_production,
                "TestRows",
                "integer"
            )
        ],

        "Original Candidate": [
            comparison_value(
                original_candidate,
                "Model"
            ),
            comparison_value(
                original_candidate,
                "Version"
            ),
            comparison_value(
                original_candidate,
                "Status"
            ),
            comparison_value(
                original_candidate,
                "RMSE",
                "metric"
            ),
            comparison_value(
                original_candidate,
                "MAE",
                "metric"
            ),
            safe_percent(
                original_governance.get(
                    "DriftPercent",
                    np.nan
                )
            ),
            str(
                original_governance.get(
                    "GovernanceRank",
                    "Not available"
                )
            ),
            str(
                original_governance.get(
                    "TestRows",
                    "Not available"
                )
            )
        ],

        "Capped Production": [
            comparison_value(
                capped_production,
                "Model"
            ),
            comparison_value(
                capped_production,
                "Version"
            ),
            comparison_value(
                capped_production,
                "Status"
            ),
            comparison_value(
                capped_production,
                "RMSE",
                "metric"
            ),
            comparison_value(
                capped_production,
                "MAE",
                "metric"
            ),
            "Not applicable",
            "1",
            comparison_value(
                capped_production,
                "TestRows",
                "integer"
            )
        ],

        "Capped Candidate": [
            comparison_value(
                capped_candidate,
                "Model"
            ),
            comparison_value(
                capped_candidate,
                "Version"
            ),
            comparison_value(
                capped_candidate,
                "Status"
            ),
            comparison_value(
                capped_candidate,
                "RMSE",
                "metric"
            ),
            comparison_value(
                capped_candidate,
                "MAE",
                "metric"
            ),
            safe_percent(
                capped_governance.get(
                    "DriftPercent",
                    np.nan
                )
            ),
            str(
                capped_governance.get(
                    "GovernanceRank",
                    "Not available"
                )
            ),
            str(
                capped_governance.get(
                    "TestRows",
                    "Not available"
                )
            )
        ]
    }
)


st.dataframe(
    comparison_table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Metric":
            st.column_config.TextColumn(
                "Metric",
                width="medium"
            ),

        "Original Production":
            st.column_config.TextColumn(
                "Original Production",
                width="medium"
            ),

        "Original Candidate":
            st.column_config.TextColumn(
                "Original Candidate",
                width="medium"
            ),

        "Capped Production":
            st.column_config.TextColumn(
                "Capped Production",
                width="medium"
            ),

        "Capped Candidate":
            st.column_config.TextColumn(
                "Capped Candidate",
                width="medium"
            )
    }
)


# ============================================================
# SECTION 2: GOVERNANCE RECOMMENDATIONS
# ============================================================

st.divider()

st.subheader(
    "Governance Recommendations"
)

st.caption(
    "The system recommendation supports review. "
    "It does not make or execute the final lifecycle decision."
)


original_column, capped_column = st.columns(
    2
)


def render_recommendation(
    container,
    dataset_type,
    lifecycle,
    governance
):

    with container:

        st.markdown(
            (
                '<div class="dataset-heading">'
                + dataset_type
                + " Dataset"
                + "</div>"
            ),
            unsafe_allow_html=True
        )

        production_label = model_label(
            lifecycle[
                "Production"
            ]
        )

        candidate_label = model_label(
            lifecycle[
                "Candidate"
            ]
        )

        evidence = governance[
            "Evidence"
        ]

        passed_checks = sum(
            bool(value)
            for value in evidence.values()
        )

        total_checks = len(
            evidence
        )

        st.markdown(
            f"""
            <div class="{governance['StyleClass']}">
                <strong style="font-size: 1.15rem;">
                    {governance['Icon']}
                    {governance['Label']}
                </strong>
                <br><br>
                <strong>Current production:</strong>
                {production_label}
                <br>
                <strong>Recommended candidate:</strong>
                {candidate_label}
                <br><br>
                <strong>Reason:</strong>
                <br>
                {governance['Narrative']}
                <br><br>
                <strong>Evidence checks passed:</strong>
                {passed_checks} of {total_checks}
                <br>
                <strong>Recommendation confidence:</strong>
                {governance['Confidence']}
            </div>
            """,
            unsafe_allow_html=True
        )

        if governance[
            "Action"
        ] == "Promote":

            st.success(
                "The candidate meets the defined "
                "read-only promotion recommendation rules."
            )

        elif governance[
            "Action"
        ] == "Review":

            st.warning(
                "Expert review is recommended before "
                "any lifecycle decision."
            )

        else:

            st.error(
                "The candidate does not currently meet "
                "the promotion recommendation rules."
            )


render_recommendation(
    container=original_column,
    dataset_type="Original",
    lifecycle=original_lifecycle,
    governance=original_governance
)


render_recommendation(
    container=capped_column,
    dataset_type="Capped",
    lifecycle=capped_lifecycle,
    governance=capped_governance
)


# ============================================================
# SECTION 3: RECOMMENDATION EVIDENCE
# ============================================================

st.divider()

st.subheader(
    "Recommendation Evidence"
)

st.caption(
    "These checks explain why each system recommendation "
    "was generated."
)


evidence_labels = {
    "Candidate is Rank 1":
        "Candidate remains Governance Rank 1",

    "RMSE stable or improved":
        "RMSE is stable or improved",

    "MAE stable or improved":
        "MAE is stable or improved",

    "Drift within 5%":
        "Absolute drift is within 5%",

    "Retraining result available":
        "Retraining result is available",

    "Test records available":
        "Test records are available"
}


evidence_rows = []


for evidence_key, evidence_label in (
    evidence_labels.items()
):

    original_passed = original_governance[
        "Evidence"
    ].get(
        evidence_key,
        False
    )

    capped_passed = capped_governance[
        "Evidence"
    ].get(
        evidence_key,
        False
    )

    if evidence_key == (
        "Test records available"
    ):

        original_detail = (
            str(
                original_governance.get(
                    "TestRows",
                    "Not available"
                )
            )
            + " records"
        )

        capped_detail = (
            str(
                capped_governance.get(
                    "TestRows",
                    "Not available"
                )
            )
            + " records"
        )

    elif evidence_key == (
        "Drift within 5%"
    ):

        original_detail = safe_percent(
            original_governance.get(
                "DriftPercent",
                np.nan
            )
        )

        capped_detail = safe_percent(
            capped_governance.get(
                "DriftPercent",
                np.nan
            )
        )

    else:

        original_detail = None
        capped_detail = None

    evidence_rows.append(
        {
            "Validation Check":
                evidence_label,

            "Original":
                evidence_result(
                    original_passed,
                    original_detail
                ),

            "Capped":
                evidence_result(
                    capped_passed,
                    capped_detail
                )
        }
    )


evidence_table = pd.DataFrame(
    evidence_rows
)


st.dataframe(
    evidence_table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Validation Check":
            st.column_config.TextColumn(
                "Validation Check",
                width="large"
            ),

        "Original":
            st.column_config.TextColumn(
                "Original Result",
                width="medium"
            ),

        "Capped":
            st.column_config.TextColumn(
                "Capped Result",
                width="medium"
            )
    }
)
# ============================================================
# SECTION 5: ACTION PREVIEW
# ============================================================

st.divider()

st.subheader(
    "Lifecycle Action Preview"
)

st.caption(
    "This section shows what would happen if a reviewer "
    "chooses Promote or Decline. No database changes are "
    "performed by this dashboard."
)

original_col, capped_col = st.columns(2)


# ============================================================
# ORIGINAL DATASET
# ============================================================

with original_col:

    st.markdown(
        """
        <div class="dataset-heading">
            Original Dataset
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### If Promote is Chosen")

    st.success(
        f"""
        Current Production

        {model_label(original_lifecycle["Production"])}

        ↓

        Status changes from Production → Retired


        Candidate

        {model_label(original_lifecycle["Candidate"])}

        ↓

        Status changes from Candidate → Production
        """
    )

    st.markdown("### If Decline is Chosen")

    st.warning(
        f"""
        Current Production

        {model_label(original_lifecycle["Production"])}

        ↓

        Remains Production


        Candidate

        {model_label(original_lifecycle["Candidate"])}

        ↓

        Status changes from Candidate → Declined
        """
    )


# ============================================================
# CAPPED DATASET
# ============================================================

with capped_col:

    st.markdown(
        """
        <div class="dataset-heading">
            Capped Dataset
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### If Promote is Chosen")

    st.success(
        f"""
        Current Production

        {model_label(capped_lifecycle["Production"])}

        ↓

        Status changes from Production → Retired


        Candidate

        {model_label(capped_lifecycle["Candidate"])}

        ↓

        Status changes from Candidate → Production
        """
    )

    st.markdown("### If Decline is Chosen")

    st.warning(
        f"""
        Current Production

        {model_label(capped_lifecycle["Production"])}

        ↓

        Remains Production


        Candidate

        {model_label(capped_lifecycle["Candidate"])}

        ↓

        Status changes from Candidate → Declined
        """
    )


# ============================================================
# ACTION SUMMARY
# ============================================================

st.info(
    """
    Action Summary

    Promote:
    - Current Production model becomes Retired
    - Candidate model becomes Production

    Decline:
    - Current Production model remains active
    - Candidate model becomes Declined

    A future version of this dashboard will allow
    authorized reviewers to execute these actions.
    """
)
# ============================================================
# SECTION 6: DECISION CONFIRMATION
# ============================================================

st.divider()

st.subheader(
    "Decision Confirmation"
)

st.caption(
    "Review the proposed lifecycle change before "
    "executing any Promote or Decline action."
)

confirm_col1, confirm_col2 = st.columns(2)

# ============================================================
# ORIGINAL DATASET
# ============================================================

with confirm_col1:

    st.markdown(
        """
        <div class="dataset-heading">
            Original Dataset
        </div>
        """,
        unsafe_allow_html=True
    )

    st.info(
        f"""
Current Production

{model_label(original_lifecycle["Production"])}

Recommended Candidate

{model_label(original_lifecycle["Candidate"])}
"""
    )

    confirmation_choice_original = st.radio(
        "Choose lifecycle action",
        [
            "No Action",
            "Promote Candidate",
            "Decline Candidate"
        ],
        key="original_confirmation_choice"
    )

    if (
        confirmation_choice_original
        == "Promote Candidate"
    ):

        st.success(
            f"""
Are you sure?

This action will:

• Retire {model_label(original_lifecycle["Production"])}

• Promote {model_label(original_lifecycle["Candidate"])}

No changes have been applied yet.
"""
        )

    elif (
        confirmation_choice_original
        == "Decline Candidate"
    ):

        st.warning(
            f"""
Are you sure?

This action will:

• Keep {model_label(original_lifecycle["Production"])}
  as Production

• Mark {model_label(original_lifecycle["Candidate"])}
  as Declined

No changes have been applied yet.
"""
        )


# ============================================================
# CAPPED DATASET
# ============================================================

with confirm_col2:

    st.markdown(
        """
        <div class="dataset-heading">
            Capped Dataset
        </div>
        """,
        unsafe_allow_html=True
    )

    st.info(
        f"""
Current Production

{model_label(capped_lifecycle["Production"])}

Recommended Candidate

{model_label(capped_lifecycle["Candidate"])}
"""
    )

    confirmation_choice_capped = st.radio(
        "Choose lifecycle action",
        [
            "No Action",
            "Promote Candidate",
            "Decline Candidate"
        ],
        key="capped_confirmation_choice"
    )

    if (
        confirmation_choice_capped
        == "Promote Candidate"
    ):

        st.success(
            f"""
Are you sure?

This action will:

• Retire {model_label(capped_lifecycle["Production"])}

• Promote {model_label(capped_lifecycle["Candidate"])}

No changes have been applied yet.
"""
        )

    elif (
        confirmation_choice_capped
        == "Decline Candidate"
    ):

        st.warning(
            f"""
Are you sure?

This action will:

• Keep {model_label(capped_lifecycle["Production"])}
  as Production

• Mark {model_label(capped_lifecycle["Candidate"])}
  as Declined

No changes have been applied yet.
"""
        )

st.info(
    """
Confirmation Mode Only

This dashboard is still operating in read-only mode.

The Promote and Decline actions have not yet been enabled.
Selecting an option only previews the intended lifecycle
change and does not update the model registry.
"""
)

# ============================================================
# SECTION 7: CONTROLLED LIFECYCLE TRANSACTIONS
# ============================================================

st.divider()

st.subheader(
    "Execute Lifecycle Decision"
)

st.caption(
    "Authorized reviewers can Promote or Decline the "
    "recommended candidate after completing the confirmation "
    "requirements below."
)


# ------------------------------------------------------------
# Initialize audit table
# ------------------------------------------------------------

def initialize_model_decision_log():

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

                DatasetType TEXT
                    NOT NULL,

                Action TEXT
                    NOT NULL,

                ProductionModelBefore TEXT,

                ProductionVersionBefore TEXT,

                CandidateModel TEXT
                    NOT NULL,

                CandidateVersion TEXT
                    NOT NULL,

                CandidateMAE REAL,

                CandidateRMSE REAL,

                GovernanceRecommendation TEXT,

                ReviewerName TEXT
                    NOT NULL,

                DecisionReason TEXT
                    NOT NULL,

                ProductionModelAfter TEXT,

                ProductionVersionAfter TEXT,

                TransactionStatus TEXT
                    NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_model_decision_dataset
            ON model_lifecycle_decision_log (
                DatasetType
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_model_decision_timestamp
            ON model_lifecycle_decision_log (
                DecisionTimestampUTC
            )
            """
        )

        conn.commit()

    finally:

        conn.close()


initialize_model_decision_log()


# ------------------------------------------------------------
# Controlled transaction function
# ------------------------------------------------------------

def execute_lifecycle_decision(
    dataset_type,
    action,
    production_row,
    candidate_row,
    governance,
    reviewer_name,
    decision_reason
):

    if action not in [
        "Promote",
        "Decline"
    ]:

        raise ValueError(
            "Lifecycle action must be Promote or Decline."
        )

    if production_row is None:

        raise ValueError(
            "The current production model is unavailable."
        )

    if candidate_row is None:

        raise ValueError(
            "The recommended candidate is unavailable."
        )

    reviewer_name = str(
        reviewer_name
    ).strip()

    decision_reason = str(
        decision_reason
    ).strip()

    if not reviewer_name:

        raise ValueError(
            "Reviewer name is required."
        )

    if not decision_reason:

        raise ValueError(
            "Decision reason is required."
        )

    production_model = str(
        production_row[
            "Model"
        ]
    )

    production_version = str(
        production_row[
            "Version"
        ]
    )

    candidate_model = str(
        candidate_row[
            "Model"
        ]
    )

    candidate_version = str(
        candidate_row[
            "Version"
        ]
    )

    candidate_mae = float(
        candidate_row[
            "MAE"
        ]
    )

    candidate_rmse = float(
        candidate_row[
            "RMSE"
        ]
    )

    decision_timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    recommendation_text = (
        governance[
            "Icon"
        ]
        + " "
        + governance[
            "Label"
        ]
    )

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        current_production = conn.execute(
            """
            SELECT
                Model,
                Version,
                Status
            FROM model_registry
            WHERE DatasetType = ?
              AND lower(trim(Status)) = 'production'
            """,
            (
                dataset_type,
            )
        ).fetchall()

        if len(
            current_production
        ) != 1:

            raise RuntimeError(
                f"{dataset_type} must have exactly one "
                "Production record before the decision."
            )

        database_production_model = str(
            current_production[0][0]
        )

        database_production_version = str(
            current_production[0][1]
        )

        if (
            database_production_model
            != production_model
            or
            database_production_version
            != production_version
        ):

            raise RuntimeError(
                "The dashboard production model is no longer "
                "consistent with the database. Refresh the "
                "page before making a decision."
            )

        current_candidate = conn.execute(
            """
            SELECT
                Model,
                Version,
                Status
            FROM model_registry
            WHERE DatasetType = ?
              AND Model = ?
              AND Version = ?
            """,
            (
                dataset_type,
                candidate_model,
                candidate_version
            )
        ).fetchall()

        if len(
            current_candidate
        ) != 1:

            raise RuntimeError(
                "The selected candidate was not found exactly "
                "once in the model registry."
            )

        candidate_status = str(
            current_candidate[0][2]
        ).strip().lower()

        if candidate_status != "candidate":

            raise RuntimeError(
                "The selected model is no longer a Candidate. "
                "Refresh the page before making a decision."
            )

        if action == "Promote":

            retired_update = conn.execute(
                """
                UPDATE model_registry
                SET Status = 'Retired'
                WHERE DatasetType = ?
                  AND Model = ?
                  AND Version = ?
                  AND lower(trim(Status)) = 'production'
                """,
                (
                    dataset_type,
                    production_model,
                    production_version
                )
            )

            if retired_update.rowcount != 1:

                raise RuntimeError(
                    "The current Production model could not "
                    "be retired safely."
                )

            promoted_update = conn.execute(
                """
                UPDATE model_registry
                SET Status = 'Production'
                WHERE DatasetType = ?
                  AND Model = ?
                  AND Version = ?
                  AND lower(trim(Status)) = 'candidate'
                """,
                (
                    dataset_type,
                    candidate_model,
                    candidate_version
                )
            )

            if promoted_update.rowcount != 1:

                raise RuntimeError(
                    "The Candidate model could not be promoted."
                )

            production_model_after = (
                candidate_model
            )

            production_version_after = (
                candidate_version
            )

        else:

            declined_update = conn.execute(
                """
                UPDATE model_registry
                SET Status = 'Declined'
                WHERE DatasetType = ?
                  AND Model = ?
                  AND Version = ?
                  AND lower(trim(Status)) = 'candidate'
                """,
                (
                    dataset_type,
                    candidate_model,
                    candidate_version
                )
            )

            if declined_update.rowcount != 1:

                raise RuntimeError(
                    "The Candidate model could not be declined."
                )

            production_model_after = (
                production_model
            )

            production_version_after = (
                production_version
            )

        final_production = conn.execute(
            """
            SELECT
                Model,
                Version
            FROM model_registry
            WHERE DatasetType = ?
              AND lower(trim(Status)) = 'production'
            """,
            (
                dataset_type,
            )
        ).fetchall()

        if len(
            final_production
        ) != 1:

            raise RuntimeError(
                f"{dataset_type} must have exactly one "
                "Production model after the decision."
            )

        if (
            str(
                final_production[0][0]
            )
            != production_model_after
            or
            str(
                final_production[0][1]
            )
            != production_version_after
        ):

            raise RuntimeError(
                "Post-decision Production model verification "
                "failed."
            )

        conn.execute(
            """
            INSERT INTO model_lifecycle_decision_log (
                DecisionTimestampUTC,
                DatasetType,
                Action,
                ProductionModelBefore,
                ProductionVersionBefore,
                CandidateModel,
                CandidateVersion,
                CandidateMAE,
                CandidateRMSE,
                GovernanceRecommendation,
                ReviewerName,
                DecisionReason,
                ProductionModelAfter,
                ProductionVersionAfter,
                TransactionStatus
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                decision_timestamp,
                dataset_type,
                action,
                production_model,
                production_version,
                candidate_model,
                candidate_version,
                candidate_mae,
                candidate_rmse,
                recommendation_text,
                reviewer_name,
                decision_reason,
                production_model_after,
                production_version_after,
                "Completed"
            )
        )

        conn.commit()

        return {
            "DatasetType":
                dataset_type,

            "Action":
                action,

            "ProductionBefore":
                (
                    production_model
                    + " "
                    + production_version
                ),

            "Candidate":
                (
                    candidate_model
                    + " "
                    + candidate_version
                ),

            "ProductionAfter":
                (
                    production_model_after
                    + " "
                    + production_version_after
                ),

            "Reviewer":
                reviewer_name,

            "TimestampUTC":
                decision_timestamp,

            "Status":
                "Completed"
        }

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# ------------------------------------------------------------
# Render action form
# ------------------------------------------------------------

def render_decision_form(
    container,
    dataset_type,
    lifecycle,
    governance,
    confirmation_choice
):

    with container:

        production_row = lifecycle[
            "Production"
        ]

        candidate_row = lifecycle[
            "Candidate"
        ]

        st.markdown(
            (
                '<div class="dataset-heading">'
                + dataset_type
                + " Dataset Decision"
                + "</div>"
            ),
            unsafe_allow_html=True
        )

        if candidate_row is None:

            st.info(
                "No recommended Candidate is currently "
                "available for this dataset."
            )

            return

        if confirmation_choice == "No Action":

            st.info(
                "Select Promote Candidate or Decline Candidate "
                "in the Decision Confirmation section above."
            )

            return

        if confirmation_choice == (
            "Promote Candidate"
        ):

            selected_action = "Promote"

            st.success(
                "You selected Promote. Complete the required "
                "review information and confirm the action."
            )

        else:

            selected_action = "Decline"

            st.warning(
                "You selected Decline. Complete the required "
                "review information and confirm the action."
            )

        with st.form(
            key=(
                "lifecycle_decision_form_"
                + dataset_type.lower()
            )
        ):

            reviewer_name = st.text_input(
                "Reviewer name",
                key=(
                    "reviewer_name_"
                    + dataset_type.lower()
                ),
                placeholder=(
                    "Enter SME, MEL specialist, "
                    "or designated reviewer name"
                )
            )

            decision_reason = st.text_area(
                "Decision reason",
                key=(
                    "decision_reason_"
                    + dataset_type.lower()
                ),
                placeholder=(
                    "Explain why the candidate should be "
                    "promoted or declined."
                ),
                height=120
            )

            acknowledgement = st.checkbox(
                (
                    "I reviewed the model comparison, "
                    "recommendation evidence, drift result, "
                    "and lifecycle impact."
                ),
                key=(
                    "decision_acknowledgement_"
                    + dataset_type.lower()
                )
            )

            exact_confirmation_text = (
                selected_action.upper()
                + " "
                + dataset_type.upper()
            )

            typed_confirmation = st.text_input(
                (
                    "Type "
                    + exact_confirmation_text
                    + " to confirm"
                ),
                key=(
                    "typed_confirmation_"
                    + dataset_type.lower()
                )
            )

            submit_decision = st.form_submit_button(
                (
                    "Confirm "
                    + selected_action
                    + " for "
                    + dataset_type
                ),
                type="primary",
                use_container_width=True
            )

        if submit_decision:

            validation_messages = []

            if not str(
                reviewer_name
            ).strip():

                validation_messages.append(
                    "Reviewer name is required."
                )

            if not str(
                decision_reason
            ).strip():

                validation_messages.append(
                    "Decision reason is required."
                )

            if not acknowledgement:

                validation_messages.append(
                    "The review acknowledgement is required."
                )

            if (
                str(
                    typed_confirmation
                ).strip().upper()
                != exact_confirmation_text
            ):

                validation_messages.append(
                    "The confirmation text does not match "
                    + exact_confirmation_text
                    + "."
                )

            if validation_messages:

                for message in validation_messages:

                    st.error(
                        message
                    )

            else:

                try:

                    result = execute_lifecycle_decision(
                        dataset_type=dataset_type,
                        action=selected_action,
                        production_row=production_row,
                        candidate_row=candidate_row,
                        governance=governance,
                        reviewer_name=reviewer_name,
                        decision_reason=decision_reason
                    )

                    st.success(
                        (
                            selected_action
                            + " completed successfully for "
                            + dataset_type
                            + "."
                        )
                    )

                    st.json(
                        result
                    )

                    st.cache_data.clear()

                    st.rerun()

                except Exception as error:

                    st.error(
                        (
                            selected_action
                            + " could not be completed. "
                            "The transaction was rolled back."
                        )
                    )

                    st.exception(
                        error
                    )


# ------------------------------------------------------------
# Render Original and Capped transaction controls
# ------------------------------------------------------------

transaction_original_col, transaction_capped_col = (
    st.columns(2)
)


render_decision_form(
    container=transaction_original_col,
    dataset_type="Original",
    lifecycle=original_lifecycle,
    governance=original_governance,
    confirmation_choice=(
        confirmation_choice_original
    )
)


render_decision_form(
    container=transaction_capped_col,
    dataset_type="Capped",
    lifecycle=capped_lifecycle,
    governance=capped_governance,
    confirmation_choice=(
        confirmation_choice_capped
    )
)


# ------------------------------------------------------------
# Decision history
# ------------------------------------------------------------

st.divider()

st.subheader(
    "Lifecycle Decision History"
)


@st.cache_data
def load_model_decision_history():

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        decision_history = pd.read_sql_query(
            """
            SELECT
                DecisionTimestampUTC,
                DatasetType,
                Action,
                ProductionModelBefore,
                ProductionVersionBefore,
                CandidateModel,
                CandidateVersion,
                GovernanceRecommendation,
                ReviewerName,
                DecisionReason,
                ProductionModelAfter,
                ProductionVersionAfter,
                TransactionStatus
            FROM model_lifecycle_decision_log
            ORDER BY
                DecisionTimestampUTC DESC,
                DecisionID DESC
            """,
            conn
        )

    finally:

        conn.close()

    return decision_history


decision_history = load_model_decision_history()


if decision_history.empty:

    st.info(
        "No Promote or Decline decisions have been "
        "recorded yet."
    )

else:

    st.dataframe(
        decision_history,
        hide_index=True,
        use_container_width=True
    )


st.warning(
    """
Lifecycle transactions are permanent registry decisions.

Before confirming an action, verify the dataset type,
production version, candidate version, recommendation,
drift result, and reviewer rationale.
"""
)



# ============================================================
# HUMAN OVERSIGHT NOTICE
# ============================================================

st.markdown(
    """
    <div class="governance-note">
        <strong>Human oversight required</strong>
        <br><br>
        These recommendations support model lifecycle
        decision-making. Final approval remains the
        responsibility of the designated SME, MEL specialist,
        or model governance reviewer.
        <br><br>
        Reviewers should consider model performance, drift,
        test coverage, data quality, operational context, and
        professional judgement before promoting or declining
        a candidate.
    </div>
    """,
    unsafe_allow_html=True
)


st.caption(
    "Read-only lifecycle governance view. "
    "No model status is changed by this page."
)

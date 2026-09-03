import streamlit as st
import pandas as pd
import altair as alt

from utils.data_utils import (
    load_dashboard_data,
    prepare_numeric_columns,
)

from utils.risk_thresholds import classify_risk


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Risk Classification Dashboard",
    page_icon="🚦",
    layout="wide",
)

st.title("🚦 Risk Classification Dashboard")

st.caption(
    "Explore current indicator risk, project forecasts, "
    "and the indicators contributing most to expected risk."
)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def safe_classify_risk(value, assessment_level):
    """
    Classify only valid numeric values.
    Missing values are classified as Unknown.
    """

    if pd.isna(value):
        return "Unknown"

    return classify_risk(
        float(value),
        assessment_level,
    )


def format_percentage(value):
    """
    Display a ratio such as 0.88 as 88.0%.
    """

    if pd.isna(value):
        return "Not available"

    return f"{value:.1%}"


def status_icon(status):
    """
    Return a visual icon for each status.
    """

    icons = {
        "On Track": "🟢",
        "At Risk": "🟡",
        "Off Track": "🔴",
        "Unknown": "⚪",
    }

    return icons.get(status, "⚪")


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

try:
    data, sheet, sheets = load_dashboard_data()
    data = prepare_numeric_columns(data)

except Exception as error:
    st.error(
        f"Unable to load monitoring data: {error}"
    )
    st.stop()


# --------------------------------------------------
# VALIDATE BASIC COLUMNS
# --------------------------------------------------

basic_required_columns = [
    "IndicatorID",
    "Project",
]

missing_basic_columns = [
    column
    for column in basic_required_columns
    if column not in data.columns
]

if missing_basic_columns:
    st.error(
        "The Risk Dashboard cannot run because these "
        "required columns are missing: "
        f"{', '.join(missing_basic_columns)}"
    )
    st.stop()


# --------------------------------------------------
# USE THE LATEST RECORD FOR EACH INDICATOR
# --------------------------------------------------

required_snapshot_columns = {
    "IndicatorID",
    "PeriodIndex",
}

if required_snapshot_columns.issubset(data.columns):

    snapshot = (
        data
        .sort_values(
            [
                "IndicatorID",
                "PeriodIndex",
            ]
        )
        .groupby(
            "IndicatorID",
            as_index=False,
        )
        .tail(1)
        .reset_index(drop=True)
    )

else:
    snapshot = data.copy()


# ==================================================
# SECTION 1: INDICATOR RISK ANALYSIS
# ==================================================

st.header("1. Indicator Risk Analysis")

st.markdown(
    "Use the filters to identify indicators that are "
    "On Track, At Risk, or Off Track at the Quarterly, "
    "Annual, or Life-of-Project level."
)


project_options = ["All Projects"] + sorted(
    snapshot["Project"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


filter_col1, filter_col2, filter_col3 = st.columns(3)


with filter_col1:

    selected_project = st.selectbox(
        "Project",
        project_options,
    )


with filter_col2:

    assessment_level = st.selectbox(
        "Assessment Level",
        [
            "Quarterly",
            "Annual",
            "LoP",
        ],
    )


with filter_col3:

    selected_status = st.selectbox(
        "Risk Status",
        [
            "All",
            "On Track",
            "At Risk",
            "Off Track",
            "Unknown",
        ],
    )


assessment_columns = {

    "Quarterly": {
        "ratio": "AchievementRatio",
        "actual": "QuarterActual",
        "target": "QuarterTarget",
    },

    "Annual": {
        "ratio": "AnnualProgress",
        "actual": "CurrentYearActual",
        "target": "AnnualTarget",
    },

    "LoP": {
        "ratio": "LoPProgress",
        "actual": "CumulativeActual",
        "target": "LoPTarget",
    },
}


selected_columns = assessment_columns[
    assessment_level
]

ratio_column = selected_columns["ratio"]
actual_column = selected_columns["actual"]
target_column = selected_columns["target"]


if ratio_column not in snapshot.columns:

    st.error(
        f"The required column '{ratio_column}' "
        "is missing from the dataset."
    )

    st.stop()


filtered_data = snapshot.copy()


if selected_project != "All Projects":

    filtered_data = filtered_data[
        filtered_data["Project"].astype(str)
        == selected_project
    ].copy()


filtered_data["RiskStatus"] = filtered_data[
    ratio

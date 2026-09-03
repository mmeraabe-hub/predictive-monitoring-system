import streamlit as st
import pandas as pd

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
    "Explore current indicator risk by project and assessment level."
)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

try:
    data, sheet, sheets = load_dashboard_data()
    data = prepare_numeric_columns(data)
except Exception as error:
    st.error(f"Unable to load monitoring data: {error}")
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
        data.sort_values(["IndicatorID", "PeriodIndex"])
        .groupby("IndicatorID", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )
else:
    snapshot = data.copy()


# --------------------------------------------------
# SECTION 1: INDICATOR RISK ANALYSIS
# --------------------------------------------------

st.header("1. Indicator Risk Analysis")

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
        ["Quarterly", "Annual", "LoP"],
    )

with filter_col3:
    selected_status = st.selectbox(
        "Risk Status",
        ["All", "On Track", "At Risk", "Off Track", "Unknown"],
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

selected_columns = assessment_columns[assessment_level]
ratio_column = selected_columns["ratio"]
actual_column = selected_columns["actual"]
target_column = selected_columns["target"]


if ratio_column not in snapshot.columns:
    st.error(
        f"The required column '{ratio_column}' is missing from the dataset."
    )
    st.stop()


filtered_data = snapshot.copy()

if selected_project != "All Projects":
    filtered_data = filtered_data[
        filtered_data["Project"].astype(str) == selected_project
    ].copy()


filtered_data["RiskStatus"] = filtered_data[ratio_column].apply(
    lambda value: classify_risk(value, assessment_level)
)


if selected_status != "All":
    filtered_data = filtered_data[
        filtered_data["RiskStatus"] == selected_status
    ].copy()


# --------------------------------------------------
# SUMMARY CARDS
# --------------------------------------------------

total_assessed = filtered_data[ratio_column].notna().sum()
on_track_count = (filtered_data["RiskStatus"] == "On Track").sum()
at_risk_count = (filtered_data["RiskStatus"] == "At Risk").sum()
off_track_count = (filtered_data["RiskStatus"] == "Off Track").sum()

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

metric_col1.metric("Indicators Assessed", int(total_assessed))
metric_col2.metric("🟢 On Track", int(on_track_count))
metric_col3.metric("🟡 At Risk", int(at_risk_count))
metric_col4.metric("🔴 Off Track", int(off_track_count))


# --------------------------------------------------
# RISK DISTRIBUTION
# --------------------------------------------------

st.subheader("Risk Distribution")

risk_order = ["On Track", "At Risk", "Off Track", "Unknown"]

risk_distribution = (
    filtered_data["RiskStatus"]
    .value_counts()
    .reindex(risk_order, fill_value=0)
    .rename_axis("Risk Status")
    .reset_index(name="Indicators")
)

st.bar_chart(
    risk_distribution.set_index("Risk Status"),
    use_container_width=True,
)


# --------------------------------------------------
# INDICATOR LIST
# --------------------------------------------------

st.subheader(f"{assessment_level} Indicator Risk List")

display_columns = [
    "Project",
    "IndicatorID",
    "IndicatorName",
    "Year",
    "Quarter",
    "PeriodLabel",
    actual_column,
    target_column,
    ratio_column,
    "RiskStatus",
]

display_columns = [
    column
    for column in display_columns
    if column in filtered_data.columns
]

display_data = filtered_data[display_columns].copy()

if ratio_column in display_data.columns:
    display_data[ratio_column] = (
        display_data[ratio_column] * 100
    ).round(1)

st.dataframe(
    display_data,
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "The ratio is displayed as a percentage. "
    "Risk classification uses the centralized thresholds "
    "defined in utils/risk_thresholds.py."
)
# ==================================================
# SECTION 2: PROJECT EARLY WARNING ANALYSIS
# ==================================================

st.divider()

st.header("📈 Project Early Warning Analysis")

project_list = sorted(
    snapshot["Project"]
    .dropna()
    .unique()
    .tolist()
)

selected_ew_project = st.selectbox(
    "Select Project for Early Warning Analysis",
    project_list,
    key="ew_project"
)

project_data = snapshot[
    snapshot["Project"] == selected_ew_project
].copy()

annual_actual = project_data["AnnualProgress"].median()
annual_forecast = project_data["AnnualForecastRatio"].median()

lop_actual = project_data["LoPProgress"].median()
lop_forecast = project_data["LoPForecastRatio"].median()

annual_status = classify_risk(
    annual_forecast,
    "Annual"
)

lop_status = classify_risk(
    lop_forecast,
    "LoP"
)

col1, col2 = st.columns(2)

with col1:

    st.metric(
        "Annual Actual Index",
        f"{annual_actual:.1%}"
    )

    st.metric(
        "Annual Forecast Index",
        f"{annual_forecast:.1%}"
    )

    st.write(
        f"Expected Annual Status: {annual_status}"
    )

with col2:

    st.metric(
        "LoP Actual Index",
        f"{lop_actual:.1%}"
    )

    st.metric(
        "LoP Forecast Index",
        f"{lop_forecast:.1%}"
    )

    st.write(
        f"Expected LoP Status: {lop_status}"
    )

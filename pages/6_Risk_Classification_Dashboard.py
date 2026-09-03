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
# SECTION 4: PROJECT PERFORMANCE TRAJECTORY
# ==================================================

st.divider()

st.header("📈 Project Actual vs AI Forecast vs Target")

st.markdown(
    "This visual compares the selected project's current "
    "achievement with its AI forecast. The red dashed line "
    "represents the 100% target benchmark."
)


# Prepare Annual and LoP trajectory data

trajectory_data = pd.DataFrame(
    [
        {
            "Assessment": "Annual",
            "Stage": "Current Actual",
            "StageOrder": 1,
            "Achievement": annual_actual * 100
            if pd.notna(annual_actual)
            else None,
        },
        {
            "Assessment": "Annual",
            "Stage": "AI Forecast",
            "StageOrder": 2,
            "Achievement": annual_forecast * 100
            if pd.notna(annual_forecast)
            else None,
        },
        {
            "Assessment": "LoP",
            "Stage": "Current Actual",
            "StageOrder": 1,
            "Achievement": lop_actual * 100
            if pd.notna(lop_actual)
            else None,
        },
        {
            "Assessment": "LoP",
            "Stage": "AI Forecast",
            "StageOrder": 2,
            "Achievement": lop_forecast * 100
            if pd.notna(lop_forecast)
            else None,
        },
    ]
)

trajectory_data = trajectory_data.dropna(
    subset=["Achievement"]
).copy()


if trajectory_data.empty:

    st.info(
        "No valid Annual or LoP values are available "
        "for the project trajectory chart."
    )

else:

    chart_upper_limit = max(
        110.0,
        float(trajectory_data["Achievement"].max()) + 10.0,
    )

    assessment_colors = alt.Scale(
        domain=["Annual", "LoP"],
        range=["#2563EB", "#16A34A"],
    )

    base_chart = alt.Chart(
        trajectory_data
    ).encode(
        x=alt.X(
            "Stage:N",
            sort=["Current Actual", "AI Forecast"],
            title=None,
            axis=alt.Axis(
                labelAngle=0,
                labelFontSize=13,
            ),
        ),
        y=alt.Y(
            "Achievement:Q",
            title="Achievement Index (%)",
            scale=alt.Scale(
                domain=[0, chart_upper_limit]
            ),
            axis=alt.Axis(
                labelExpr="datum.value + '%'",
                grid=True,
            ),
        ),
        color=alt.Color(
            "Assessment:N",
            title=None,
            scale=assessment_colors,
            legend=alt.Legend(
                orient="top",
                direction="horizontal",
            ),
        ),
        detail="Assessment:N",
    )

    trajectory_lines = base_chart.mark_line(
        strokeWidth=4,
    )

    trajectory_points = base_chart.mark_point(
        filled=True,
        size=190,
        stroke="white",
        strokeWidth=2,
    ).encode(
        tooltip=[
            alt.Tooltip(
                "Assessment:N",
                title="Assessment",
            ),
            alt.Tooltip(
                "Stage:N",
                title="Stage",
            ),
            alt.Tooltip(
                "Achievement:Q",
                title="Achievement Index (%)",
                format=".1f",
            ),
        ]
    )

    point_labels = base_chart.mark_text(
        dy=-18,
        fontSize=13,
        fontWeight="bold",
    ).encode(
        text=alt.Text(
            "Achievement:Q",
            format=".1f",
        )
    )

    target_data = pd.DataFrame(
        {
            "Target": [100.0],
        }
    )

    target_line = alt.Chart(
        target_data
    ).mark_rule(
        color="#DC2626",
        strokeWidth=3,
        strokeDash=[8, 6],
    ).encode(
        y=alt.Y(
            "Target:Q"
        ),
        tooltip=[
            alt.Tooltip(
                "Target:Q",
                title="Target Index (%)",
                format=".1f",
            )
        ],
    )

    target_label_data = pd.DataFrame(
        {
            "Stage": ["AI Forecast"],
            "Target": [100.0],
            "Label": ["Target: 100%"],
        }
    )

    target_label = alt.Chart(
        target_label_data
    ).mark_text(
        color="#DC2626",
        align="right",
        dx=-8,
        dy=-10,
        fontSize=13,
        fontWeight="bold",
    ).encode(
        x=alt.X(
            "Stage:N",
            sort=["Current Actual", "AI Forecast"],
        ),
        y=alt.Y(
            "Target:Q"
        ),
        text="Label:N",
    )

    professional_line_chart = (
        trajectory_lines
        + trajectory_points
        + point_labels
        + target_line
        + target_label
    ).properties(
        height=430,
        title=(
            f"{selected_ew_project}: "
            "Current Achievement to AI Forecast"
        ),
    ).configure_view(
        strokeWidth=0,
    ).configure_title(
        fontSize=17,
        anchor="start",
        color="#1F2937",
    )

    st.altair_chart(
        professional_line_chart,
        use_container_width=True,
    )

    st.caption(
        "Blue shows the Annual trajectory, green shows the "
        "Life-of-Project trajectory, and the red dashed line "
        "shows the 100% target. A forecast point below the target "
        "indicates an expected achievement gap."
    )


# --------------------------------------------------
# FORECAST GAP CARDS
# --------------------------------------------------

annual_gap_column, lop_gap_column = st.columns(2)


with annual_gap_column:

    if pd.isna(annual_forecast):

        st.metric(
            "Annual Gap to Target",
            "Not available",
        )

    else:

        annual_gap_to_target = (
            annual_forecast - 1.0
        ) * 100

        st.metric(
            "Annual Forecast Gap",
            f"{annual_gap_to_target:+.1f} percentage points",
        )


with lop_gap_column:

    if pd.isna(lop_forecast):

        st.metric(
            "LoP Gap to Target",
            "Not available",
        )

    else:

        lop_gap_to_target = (
            lop_forecast - 1.0
        ) * 100

        st.metric(
            "LoP Forecast Gap",
            f"{lop_gap_to_target:+.1f} percentage points",
        )

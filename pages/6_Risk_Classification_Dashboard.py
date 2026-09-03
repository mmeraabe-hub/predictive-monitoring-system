import streamlit as st
import pandas as pd
import altair as alt

from utils.data_utils import (
    load_dashboard_data,
    prepare_numeric_columns,
)

from utils.risk_thresholds import classify_risk


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Risk Classification Dashboard",
    page_icon="🚦",
    layout="wide",
)

st.title("🚦 Risk Classification Dashboard")

st.caption(
    "Explore current indicator risk, project early-warning forecasts, "
    "and the indicators contributing most to expected project risk."
)


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def safe_classify_risk(value, assessment_level):
    """
    Apply the centralized risk classification only to valid values.
    """

    if pd.isna(value):
        return "Unknown"

    return classify_risk(
        float(value),
        assessment_level,
    )


def format_percentage(value):
    """
    Convert a ratio such as 0.88 to 88.0%.
    """

    if pd.isna(value):
        return "Not available"

    return f"{float(value):.1%}"


def status_icon(status):
    """
    Return an icon for each risk status.
    """

    icons = {
        "On Track": "🟢",
        "At Risk": "🟡",
        "Off Track": "🔴",
        "Unknown": "⚪",
    }

    return icons.get(status, "⚪")


def status_message(status):
    """
    Create a short management interpretation.
    """

    messages = {
        "On Track": (
            "The forecast meets the On Track threshold."
        ),
        "At Risk": (
            "The forecast shows progress, but management attention "
            "may be needed to achieve the expected target."
        ),
        "Off Track": (
            "The forecast indicates a substantial target gap and "
            "may require timely corrective action."
        ),
        "Unknown": (
            "The available data is insufficient to classify the forecast."
        ),
    }

    return messages.get(
        status,
        messages["Unknown"],
    )


# ==================================================
# LOAD DATA
# ==================================================

try:
    data, sheet, sheets = load_dashboard_data()
    data = prepare_numeric_columns(data)

except Exception as error:
    st.error(
        f"Unable to load monitoring data: {error}"
    )
    st.stop()


# ==================================================
# VALIDATE BASIC DATA STRUCTURE
# ==================================================

required_basic_columns = [
    "IndicatorID",
    "Project",
]

missing_basic_columns = [
    column
    for column in required_basic_columns
    if column not in data.columns
]

if missing_basic_columns:
    st.error(
        "The dashboard cannot run because these required columns "
        f"are missing: {', '.join(missing_basic_columns)}"
    )
    st.stop()


# ==================================================
# CREATE LATEST INDICATOR SNAPSHOT
# ==================================================

if "PeriodIndex" in data.columns:

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
    "Use the filters to identify indicators that are On Track, "
    "At Risk, Off Track, or Unknown at the Quarterly, Annual, "
    "or Life-of-Project assessment level."
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
        key="indicator_risk_project",
    )


with filter_col2:

    assessment_level = st.selectbox(
        "Assessment Level",
        [
            "Quarterly",
            "Annual",
            "LoP",
        ],
        key="indicator_assessment_level",
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
        key="indicator_risk_status",
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


selected_assessment_columns = assessment_columns[
    assessment_level
]

ratio_column = selected_assessment_columns["ratio"]
actual_column = selected_assessment_columns["actual"]
target_column = selected_assessment_columns["target"]


if ratio_column not in snapshot.columns:
    st.error(
        f"The required column '{ratio_column}' is missing "
        "from the monitoring dataset."
    )
    st.stop()


indicator_risk_data = snapshot.copy()


if selected_project != "All Projects":

    indicator_risk_data = indicator_risk_data[
        indicator_risk_data["Project"].astype(str)
        == selected_project
    ].copy()


indicator_risk_data["RiskStatus"] = indicator_risk_data[
    ratio_column
].apply(
    lambda value: safe_classify_risk(
        value,
        assessment_level,
    )
)


# Keep a copy before applying the status filter.
# This allows the summary cards to show the full distribution.

summary_data = indicator_risk_data.copy()


total_assessed = int(
    summary_data[ratio_column]
    .notna()
    .sum()
)

on_track_count = int(
    (
        summary_data["RiskStatus"]
        == "On Track"
    ).sum()
)

at_risk_count = int(
    (
        summary_data["RiskStatus"]
        == "At Risk"
    ).sum()
)

off_track_count = int(
    (
        summary_data["RiskStatus"]
        == "Off Track"
    ).sum()
)


if selected_status != "All":

    indicator_risk_data = indicator_risk_data[
        indicator_risk_data["RiskStatus"]
        == selected_status
    ].copy()


# --------------------------------------------------
# SUMMARY CARDS
# --------------------------------------------------

metric_col1, metric_col2, metric_col3, metric_col4 = (
    st.columns(4)
)

metric_col1.metric(
    "Indicators Assessed",
    total_assessed,
)

metric_col2.metric(
    "🟢 On Track",
    on_track_count,
)

metric_col3.metric(
    "🟡 At Risk",
    at_risk_count,
)

metric_col4.metric(
    "🔴 Off Track",
    off_track_count,
)


# --------------------------------------------------
# RISK DISTRIBUTION
# --------------------------------------------------

st.subheader("Risk Distribution")


risk_order = [
    "On Track",
    "At Risk",
    "Off Track",
    "Unknown",
]


risk_distribution = (
    summary_data["RiskStatus"]
    .value_counts()
    .reindex(
        risk_order,
        fill_value=0,
    )
    .rename_axis("Risk Status")
    .reset_index(name="Indicators")
)


risk_distribution_chart = (
    alt.Chart(risk_distribution)
    .mark_bar(
        cornerRadiusTopLeft=5,
        cornerRadiusTopRight=5,
    )
    .encode(
        x=alt.X(
            "Risk Status:N",
            sort=risk_order,
            title=None,
            axis=alt.Axis(
                labelAngle=0,
            ),
        ),
        y=alt.Y(
            "Indicators:Q",
            title="Number of Indicators",
        ),
        color=alt.Color(
            "Risk Status:N",
            scale=alt.Scale(
                domain=risk_order,
                range=[
                    "#16A34A",
                    "#F59E0B",
                    "#DC2626",
                    "#94A3B8",
                ],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip(
                "Risk Status:N",
                title="Status",
            ),
            alt.Tooltip(
                "Indicators:Q",
                title="Indicators",
            ),
        ],
    )
    .properties(
        height=300,
    )
)


st.altair_chart(
    risk_distribution_chart,
    use_container_width=True,
)


# --------------------------------------------------
# INDICATOR RISK LIST
# --------------------------------------------------

st.subheader(
    f"{assessment_level} Indicator Risk List"
)


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
    if column in indicator_risk_data.columns
]


display_data = indicator_risk_data[
    display_columns
].copy()


if ratio_column in display_data.columns:

    display_data[
        f"{assessment_level} Achievement Index (%)"
    ] = (
        display_data[ratio_column] * 100
    ).round(1)

    display_data = display_data.drop(
        columns=[ratio_column]
    )


st.dataframe(
    display_data,
    hide_index=True,
    use_container_width=True,
)


st.caption(
    "The achievement index is displayed as a percentage. "
    "The same centralized threshold rules are used throughout "
    "the Risk, Project, and Indicator dashboards."
)


# ==================================================
# SECTION 2: PROJECT EARLY WARNING ANALYSIS
# ==================================================

st.divider()

st.header("2. Project Early Warning Analysis")

st.markdown(
    "This analysis compares the selected project's current "
    "achievement with its forecasted Annual and "
    "Life-of-Project achievement."
)


early_warning_projects = sorted(
    snapshot["Project"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


if not early_warning_projects:
    st.warning(
        "No projects are available for early-warning analysis."
    )
    st.stop()


selected_ew_project = st.selectbox(
    "Select Project for Early Warning Analysis",
    early_warning_projects,
    key="early_warning_project",
)


project_data = snapshot[
    snapshot["Project"].astype(str)
    == selected_ew_project
].copy()


early_warning_columns = [
    "AnnualProgress",
    "AnnualForecastRatio",
    "LoPProgress",
    "LoPForecastRatio",
]


missing_early_warning_columns = [
    column
    for column in early_warning_columns
    if column not in project_data.columns
]


if missing_early_warning_columns:
    st.error(
        "Early-warning analysis cannot run because these "
        "columns are missing: "
        f"{', '.join(missing_early_warning_columns)}"
    )
    st.stop()


# ==================================================
# CALCULATE PROJECT-LEVEL INDICES
# ==================================================

# Indicators may use different units, such as people,
# percentages, hectares, or facilities.
# The dashboard therefore aggregates normalized achievement
# ratios rather than adding raw indicator values.
#
# The median is used to reduce the influence of unusually
# high or unusually low indicator values.

annual_actual = project_data[
    "AnnualProgress"
].median(skipna=True)

annual_forecast = project_data[
    "AnnualForecastRatio"
].median(skipna=True)

lop_actual = project_data[
    "LoPProgress"
].median(skipna=True)

lop_forecast = project_data[
    "LoPForecastRatio"
].median(skipna=True)


annual_forecast_status = safe_classify_risk(
    annual_forecast,
    "Annual",
)

lop_forecast_status = safe_classify_risk(
    lop_forecast,
    "LoP",
)


# --------------------------------------------------
# EARLY-WARNING SUMMARY
# --------------------------------------------------

st.subheader(
    f"Early Warning Summary: {selected_ew_project}"
)


annual_column, lop_column = st.columns(2)


with annual_column:

    st.markdown("### Annual Outlook")

    annual_metric_1, annual_metric_2 = st.columns(2)

    annual_metric_1.metric(
        "Current Annual Index",
        format_percentage(annual_actual),
    )

    annual_metric_2.metric(
        "AI Forecast Annual Index",
        format_percentage(annual_forecast),
    )

    st.info(
        f"{status_icon(annual_forecast_status)} "
        f"Expected Annual Status: "
        f"{annual_forecast_status}\n\n"
        f"{status_message(annual_forecast_status)}"
    )


with lop_column:

    st.markdown("### Life-of-Project Outlook")

    lop_metric_1, lop_metric_2 = st.columns(2)

    lop_metric_1.metric(
        "Current LoP Index",
        format_percentage(lop_actual),
    )

    lop_metric_2.metric(
        "AI Forecast LoP Index",
        format_percentage(lop_forecast),
    )

    st.info(
        f"{status_icon(lop_forecast_status)} "
        f"Expected LoP Status: "
        f"{lop_forecast_status}\n\n"
        f"{status_message(lop_forecast_status)}"
    )


# ==================================================
# SECTION 3: PROFESSIONAL PROJECT TRAJECTORY CHART
# ==================================================

st.subheader(
    "Actual vs AI Forecast vs Target"
)

st.markdown(
    "The solid lines show the movement from current achievement "
    "to forecasted achievement. The red dashed line is the "
    "100% target benchmark."
)


trajectory_records = []


if pd.notna(annual_actual):

    trajectory_records.append(
        {
            "Assessment": "Annual",
            "Stage": "Current Actual",
            "StageOrder": 1,
            "Achievement": float(
                annual_actual * 100
            ),
        }
    )


if pd.notna(annual_forecast):

    trajectory_records.append(
        {
            "Assessment": "Annual",
            "Stage": "AI Forecast",
            "StageOrder": 2,
            "Achievement": float(
                annual_forecast * 100
            ),
        }
    )


if pd.notna(lop_actual):

    trajectory_records.append(
        {
            "Assessment": "LoP",
            "Stage": "Current Actual",
            "StageOrder": 1,
            "Achievement": float(
                lop_actual * 100
            ),
        }
    )


if pd.notna(lop_forecast):

    trajectory_records.append(
        {
            "Assessment": "LoP",
            "Stage": "AI Forecast",
            "StageOrder": 2,
            "Achievement": float(
                lop_forecast * 100
            ),
        }
    )


trajectory_data = pd.DataFrame(
    trajectory_records
)


if trajectory_data.empty:

    st.info(
        "No valid Annual or LoP values are available "
        "for the trajectory chart."
    )

else:

    chart_maximum = max(
        110.0,
        float(
            trajectory_data["Achievement"].max()
        ) + 10.0,
    )


    assessment_color_scale = alt.Scale(
        domain=[
            "Annual",
            "LoP",
        ],
        range=[
            "#2563EB",
            "#16A34A",
        ],
    )


    trajectory_base = (
        alt.Chart(trajectory_data)
        .encode(
            x=alt.X(
                "Stage:N",
                sort=[
                    "Current Actual",
                    "AI Forecast",
                ],
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
                    domain=[
                        0,
                        chart_maximum,
                    ]
                ),
                axis=alt.Axis(
                    labelExpr="datum.value + '%'",
                    grid=True,
                ),
            ),
            color=alt.Color(
                "Assessment:N",
                scale=assessment_color_scale,
                title=None,
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                ),
            ),
            detail="Assessment:N",
        )
    )


    trajectory_lines = (
        trajectory_base
        .mark_line(
            strokeWidth=4,
        )
    )


    trajectory_points = (
        trajectory_base
        .mark_point(
            filled=True,
            size=200,
            stroke="white",
            strokeWidth=2,
        )
        .encode(
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
    )


    trajectory_labels = (
        trajectory_base
        .mark_text(
            dy=-18,
            fontSize=13,
            fontWeight="bold",
        )
        .encode(
            text=alt.Text(
                "Achievement:Q",
                format=".1f",
            )
        )
    )


    target_data = pd.DataFrame(
        {
            "Target": [
                100.0,
            ],
        }
    )


    target_line = (
        alt.Chart(target_data)
        .mark_rule(
            color="#DC2626",
            strokeWidth=3,
            strokeDash=[
                8,
                6,
            ],
        )
        .encode(
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
    )


    target_label_data = pd.DataFrame(
        {
            "Stage": [
                "AI Forecast",
            ],
            "Target": [
                100.0,
            ],
            "TargetLabel": [
                "Target: 100%",
            ],
        }
    )


    target_label = (
        alt.Chart(target_label_data)
        .mark_text(
            color="#DC2626",
            align="right",
            dx=-8,
            dy=-10,
            fontSize=13,
            fontWeight="bold",
        )
        .encode(
            x=alt.X(
                "Stage:N",
                sort=[
                    "Current Actual",
                    "AI Forecast",
                ],
            ),
            y=alt.Y(
                "Target:Q"
            ),
            text="TargetLabel:N",
        )
    )


    professional_line_chart = (
        trajectory_lines
        + trajectory_points
        + trajectory_labels
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
        "Blue represents the Annual trajectory, green represents "
        "the Life-of-Project trajectory, and the red dashed line "
        "represents the 100% target. A forecast below the red line "
        "indicates an expected target gap."
    )


# --------------------------------------------------
# PROJECT FORECAST GAP CARDS
# --------------------------------------------------

annual_gap_column, lop_gap_column = st.columns(2)


with annual_gap_column:

    if pd.isna(annual_forecast):

        st.metric(
            "Annual Forecast Gap",
            "Not available",
        )

    else:

        annual_gap_to_target = (
            float(annual_forecast) - 1.0
        ) * 100

        st.metric(
            "Annual Forecast Gap",
            f"{annual_gap_to_target:+.1f} percentage points",
        )


with lop_gap_column:

    if pd.isna(lop_forecast):

        st.metric(
            "LoP Forecast Gap",
            "Not available",
        )

    else:

        lop_gap_to_target = (
            float(lop_forecast) - 1.0
        ) * 100

        st.metric(
            "LoP Forecast Gap",
            f"{lop_gap_to_target:+.1f} percentage points",
        )


# ==================================================
# SECTION 4: WHY IS THE PROJECT AT RISK?
# ==================================================

st.divider()

st.header("3. Why Is the Project At Risk?")

st.markdown(
    "This section identifies indicators with the largest "
    "forecast gap from the 100% target. These indicators "
    "may be priorities for management investigation and action."
)


risk_driver_level = st.radio(
    "Risk Driver Analysis Level",
    [
        "Annual",
        "LoP",
    ],
    horizontal=True,
    key="risk_driver_analysis_level",
)


if risk_driver_level == "Annual":

    forecast_column = "AnnualForecastRatio"
    driver_assessment_level = "Annual"

else:

    forecast_column = "LoPForecastRatio"
    driver_assessment_level = "LoP"


risk_driver_data = project_data.copy()


risk_driver_data = risk_driver_data.dropna(
    subset=[
        forecast_column,
    ]
).copy()


risk_driver_data["ForecastStatus"] = risk_driver_data[
    forecast_column
].apply(
    lambda value: safe_classify_risk(
        value,
        driver_assessment_level,
    )
)


risk_driver_data["GapToTarget"] = (
    1.0
    - risk_driver_data[forecast_column]
)


# Keep only indicators forecasted below the 100% target.

risk_driver_data = risk_driver_data[
    risk_driver_data["GapToTarget"] > 0
].copy()


risk_driver_data = risk_driver_data.sort_values(
    "GapToTarget",
    ascending=False,
)


top_risk_indicators = (
    risk_driver_data
    .head(10)
    .copy()
)


if top_risk_indicators.empty:

    st.success(
        "No indicators forecasted below the 100% target "
        f"were found for {selected_ew_project} at the "
        f"{risk_driver_level} level."
    )

else:

    st.warning(
        f"The indicators below have the largest "
        f"{risk_driver_level} forecast gaps for "
        f"{selected_ew_project}."
    )


    risk_display_columns = [
        "IndicatorID",
        "IndicatorName",
        forecast_column,
        "GapToTarget",
        "ForecastStatus",
    ]


    risk_display_columns = [
        column
        for column in risk_display_columns
        if column in top_risk_indicators.columns
    ]


    risk_display = top_risk_indicators[
        risk_display_columns
    ].copy()


    risk_display["Forecast Index (%)"] = (
        risk_display[forecast_column] * 100
    ).round(1)


    risk_display[
        "Gap to Target (percentage points)"
    ] = (
        risk_display["GapToTarget"] * 100
    ).round(1)


    final_risk_table_columns = [
        "IndicatorID",
        "IndicatorName",
        "Forecast Index (%)",
        "Gap to Target (percentage points)",
        "ForecastStatus",
    ]


    final_risk_table_columns = [
        column
        for column in final_risk_table_columns
        if column in risk_display.columns
    ]


    st.dataframe(
        risk_display[
            final_risk_table_columns
        ],
        hide_index=True,
        use_container_width=True,
    )


    # --------------------------------------------------
    # RISK DRIVER VISUAL
    # --------------------------------------------------

    st.subheader(
        "Indicators Contributing Most to Forecasted Risk"
    )


    risk_driver_chart = (
        alt.Chart(risk_display)
        .mark_bar(
            color="#D97706",
            cornerRadiusEnd=5,
        )
        .encode(
            y=alt.Y(
                "IndicatorID:N",
                sort="-x",
                title="Indicator",
            ),
            x=alt.X(
                "Gap to Target (percentage points):Q",
                title=(
                    "Forecast Gap to Target "
                    "(percentage points)"
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "IndicatorID:N",
                    title="Indicator ID",
                ),
                alt.Tooltip(
                    "IndicatorName:N",
                    title="Indicator",
                ),
                alt.Tooltip(
                    "Forecast Index (%):Q",
                    title="Forecast Index (%)",
                    format=".1f",
                ),
                alt.Tooltip(
                    "Gap to Target (percentage points):Q",
                    title="Gap to Target",
                    format=".1f",
                ),
                alt.Tooltip(
                    "ForecastStatus:N",
                    title="Expected Status",
                ),
            ],
        )
        .properties(
            height=max(
                300,
                len(risk_display) * 40,
            ),
        )
    )


    risk_driver_labels = (
        alt.Chart(risk_display)
        .mark_text(
            align="left",
            baseline="middle",
            dx=5,
            fontSize=12,
        )
        .encode(
            y=alt.Y(
                "IndicatorID:N",
                sort="-x",
            ),
            x=alt.X(
                "Gap to Target (percentage points):Q",
            ),
            text=alt.Text(
                "Gap to Target (percentage points):Q",
                format=".1f",
            ),
        )
    )


    st.altair_chart(
        risk_driver_chart
        + risk_driver_labels,
        use_container_width=True,
    )


    st.caption(
        "Longer bars indicate a larger forecast gap from "
        "the target. The chart is limited to the ten indicators "
        "with the largest forecast gaps."
    )


# ==================================================
# THRESHOLD TRANSPARENCY
# ==================================================

with st.expander(
    "View Risk Classification Rules"
):

    st.markdown(
        """
        **Quarterly**

        - 🟢 On Track: 90% or higher
        - 🟡 At Risk: 70% to below 90%
        - 🔴 Off Track: Below 70%

        **Annual**

        - 🟢 On Track: 95% or higher
        - 🟡 At Risk: 80% to below 95%
        - 🔴 Off Track: Below 80%

        **Life-of-Project**

        - 🟢 On Track: 100% or higher
        - 🟡 At Risk: 85% to below 100%
        - 🔴 Off Track: Below 85%
        """
    )

import streamlit as st
import pandas as pd
import altair as alt

from utils.data_utils import (
    prepare_numeric_columns,
)

from utils.database_utils import (
    load_dashboard_data_sqlite
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
st.markdown("### Risk Classification Rules")

rule_col1, rule_col2, rule_col3 = st.columns(3)

rule_col1.markdown(
    """
**Quarterly**

🟢 ≥ 90%  
🟡 70% - 89%  
🔴 < 70%
"""
)

rule_col2.markdown(
    """
**Annual**

🟢 ≥ 95%  
🟡 80% - 94%  
🔴 < 80%
"""
)

rule_col3.markdown(
    """
**Life-of-Project**

🟢 ≥ 100%  
🟡 85% - 99%  
🔴 < 85%
"""
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
    data = load_dashboard_data_sqlite()

    sheet = "dashboard_data"

    sheets = [
        "dashboard_data"
    ]

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

  
# ==================================================
# SECTION 2: PROJECT EARLY WARNING CENTER
# ==================================================

st.header("🚨 Project Early Warning Center")

st.markdown(
    """
    This executive view highlights whether a project is likely to
    achieve its year-end and life-of-project targets based on
    current implementation performance.

    Focus attention on projects requiring management action.
    """
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
    "Select Project",
    early_warning_projects,
    key="early_warning_project",
)

project_data = snapshot[
    snapshot["Project"].astype(str)
    == selected_ew_project
].copy()

required_columns = [
    "AnnualForecastRatio",
    "LoPForecastRatio",
]

missing_columns = [
    c
    for c in required_columns
    if c not in project_data.columns
]

if missing_columns:
    st.error(
        "Missing required columns: "
        + ", ".join(missing_columns)
    )
    st.stop()

for column_name in [
    "AnnualForecastRatio",
    "LoPForecastRatio",
]:
    project_data[column_name] = pd.to_numeric(
        project_data[column_name],
        errors="coerce",
    )

annual_projection = project_data[
    "AnnualForecastRatio"
].median(skipna=True)

lop_projection = project_data[
    "LoPForecastRatio"
].median(skipna=True)

annual_status = safe_classify_risk(
    annual_projection,
    "Annual",
)

lop_status = safe_classify_risk(
    lop_projection,
    "LoP",
)

# --------------------------------------------------
# OVERALL PROJECT STATUS
# --------------------------------------------------

status_priority = {
    "Off Track": 3,
    "At Risk": 2,
    "On Track": 1,
    "Unknown": 0,
}

overall_status = (
    annual_status
    if status_priority.get(
        annual_status,
        0
    )
    >= status_priority.get(
        lop_status,
        0
    )
    else lop_status
)

status_color = {
    "On Track": "#16A34A",
    "At Risk": "#F59E0B",
    "Off Track": "#DC2626",
    "Unknown": "#64748B",
}

st.markdown(
    f"""
    <div style="
        background-color:{status_color.get(overall_status,'#64748B')};
        padding:20px;
        border-radius:10px;
        color:white;
        text-align:center;
        ">
        <h2>{overall_status}</h2>
        <h4>{selected_ew_project}</h4>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# --------------------------------------------------
# EXECUTIVE SCORECARD
# --------------------------------------------------

status_display_labels = {
    "On Track": "🟢 On Track",
    "At Risk": "🟡 At Risk",
    "Off Track": "🔴 Off Track",
    "Unknown": "⚪ Data Insufficient",
}

annual_outlook_display = (
    "No Projection Available"
    if pd.isna(annual_projection)
    else format_percentage(annual_projection)
)

lop_outlook_display = (
    "No Projection Available"
    if pd.isna(lop_projection)
    else format_percentage(lop_projection)
)

annual_status_display = status_display_labels.get(
    annual_status,
    "⚪ Data Insufficient",
)

lop_status_display = status_display_labels.get(
    lop_status,
    "⚪ Data Insufficient",
)

score_col1, score_col2, score_col3, score_col4 = st.columns(4)

with score_col1:

    st.markdown(
        """
        <div style="font-weight:600;font-size:15px;">
        Year-End Outlook
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="font-size:18px;color:#64748B;">
        {annual_outlook_display}
        </div>
        """,
        unsafe_allow_html=True,
    )

with score_col2:

    st.markdown(
        """
        <div style="font-weight:600;font-size:15px;">
        Completion Outlook
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="font-size:18px;color:#111827;">
        {lop_outlook_display}
        </div>
        """,
        unsafe_allow_html=True,
    )

with score_col3:

    st.markdown(
        """
        <div style="font-weight:600;font-size:15px;">
        Annual Status
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="font-size:18px;color:#64748B;">
        {annual_status_display}
        </div>
        """,
        unsafe_allow_html=True,
    )

score_col1, score_col2, score_col3, score_col4 = st.columns(4)
with score_col4:

    st.markdown(
        """
        <div style="font-weight:600;font-size:15px;">
        LoP Status
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="font-size:18px;color:#111827;">
        {lop_status_display}
        </div>
        """,
        unsafe_allow_html=True,
    )

## --------------------------------------------------
# PROJECT DATA READINESS
# --------------------------------------------------

st.subheader("Project Data Readiness")

total_project_indicators = len(project_data)

available_annual_projections = int(
    project_data["AnnualForecastRatio"]
    .notna()
    .sum()
)

missing_annual_projections = int(
    project_data["AnnualForecastRatio"]
    .isna()
    .sum()
)

if total_project_indicators > 0:

    available_percentage = (
        available_annual_projections
        / total_project_indicators
        * 100
    )

    missing_percentage = (
        missing_annual_projections
        / total_project_indicators
        * 100
    )

else:

    available_percentage = 0.0
    missing_percentage = 0.0

readiness_col1, readiness_col2, readiness_col3 = st.columns(3)

readiness_col1.metric(
    "Indicators Reviewed",
    total_project_indicators,
)

readiness_col2.metric(
    "Forecast Available",
    f"{available_percentage:.1f}%",
)

readiness_col3.metric(
    "Data Insufficient",
    f"{missing_percentage:.1f}%",
)

availability_data = pd.DataFrame(
    {
        "Data Status": [
            "Forecast Available",
            "Data Insufficient",
        ],
        "Percentage": [
            available_percentage,
            missing_percentage,
        ],
    }
)

availability_chart = (
    alt.Chart(
        availability_data
    )
    .mark_bar(
        cornerRadius=8
    )
    .encode(
        y=alt.Y(
            "Data Status:N",
            sort=None,
            title=None,
        ),
        x=alt.X(
            "Percentage:Q",
            title="Percent of Indicators",
            scale=alt.Scale(
                domain=[0, 100]
            ),
        ),
        color=alt.Color(
            "Data Status:N",
            scale=alt.Scale(
                domain=[
                    "Forecast Available",
                    "Data Insufficient",
                ],
                range=[
                    "#16A34A",
                    "#94A3B8",
                ],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip(
                "Data Status:N",
                title="Status",
            ),
            alt.Tooltip(
                "Percentage:Q",
                title="Percentage",
                format=".1f",
            ),
        ],
    )
    .properties(
        height=120,
    )
)

st.altair_chart(
    availability_chart,
    use_container_width=True,
)

if available_percentage >= 80:

    st.success(
        f"Data Readiness: {available_percentage:.0f}%  |  High confidence forecast."
    )

elif available_percentage >= 50:

    st.warning(
        f"Data Readiness: {available_percentage:.0f}%  |  Moderate confidence forecast."
    )

else:

    st.error(
        f"Data Readiness: {available_percentage:.0f}%  |  Low confidence forecast due to missing data."
    )
# --------------------------------------------------
# MANAGEMENT ALERTS
# --------------------------------------------------

st.subheader(
    "Management Alert"
)

if annual_status == "Unknown" and lop_status == "Unknown":
    st.warning(
        """
        Data is insufficient to determine the project's year-end
        and completion outlooks.

        Management should prioritize completion and validation of
        missing monitoring data before making a performance decision.
        """
    )

elif annual_status == "Unknown":
    st.info(
        """
        The year-end outlook cannot currently be determined because
        sufficient annual projection data is unavailable.

        The completion outlook is available, but management should
        interpret the overall project status with caution and address
        the annual data gaps.
        """
    )

elif lop_status == "Unknown":
    st.info(
        """
        The project completion outlook cannot currently be determined
        because sufficient Life-of-Project projection data is unavailable.

        Management should address the missing data before relying on
        the overall completion assessment.
        """
    )

elif overall_status == "Off Track":
    st.error(
        """
        Immediate management attention is recommended.

        Current projections indicate that the project may not achieve
        planned targets unless corrective actions are implemented.
        """
    )

elif overall_status == "At Risk":
    st.warning(
        """
        Performance should be monitored closely.

        Current projections suggest a moderate risk of underachieving
        planned targets. Management should review the priority indicators
        and agree on corrective actions.
        """
    )

else:
    st.success(
        """
        Current projections indicate that the project is broadly
        on track to achieve planned targets.
        """
    )

# --------------------------------------------------
# TOP RISK INDICATORS
# --------------------------------------------------

st.subheader(
    "Priority Indicators Requiring Attention"
)

if (
    "IndicatorName" in project_data.columns
    and "AnnualProgress" in project_data.columns
):

    risk_table = project_data.copy()

    risk_table["RiskStatus"] = risk_table[
        "AnnualProgress"
    ].apply(
        lambda x: safe_classify_risk(
            x,
            "Annual",
        )
    )

    risk_table = risk_table[
        risk_table["RiskStatus"].isin(
            [
                "At Risk",
                "Off Track",
            ]
        )
    ]

    columns_to_show = [
        c
        for c in [
            "IndicatorID",
            "IndicatorName",
            "AnnualProgress",
            "RiskStatus",
        ]
        if c in risk_table.columns
    ]

    st.dataframe(
        risk_table[
            columns_to_show
        ],
        hide_index=True,
        use_container_width=True,
    )
# Variables used by Section 3 trajectory chart

annual_actual = project_data[
    "AnnualProgress"
].median(skipna=True)

annual_forecast = annual_projection

lop_actual = project_data[
    "LoPProgress"
].median(skipna=True)

lop_forecast = lop_projection
# ==================================================
# SECTION 3: PROFESSIONAL PROJECT TRAJECTORY CHART
# ==================================================

st.subheader(
    "Current Progress vs Projected Achievement vs Target"
)

st.markdown(
    "The solid lines show the movement from current achievement "
    "to projected achievement. The red dashed line is the "
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
            "Stage": "Projected Achievement",
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
            "Stage": "Projected Achievement",
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
                    "Projected Achievement",
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
                "Projected Achievement",
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
                    "Projected Achievement",
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
            "Current Performance Trajectory"
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

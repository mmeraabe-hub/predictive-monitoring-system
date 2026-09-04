import io

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_utils import (
    load_dashboard_data,
    prepare_numeric_columns,
    create_period_snapshot
)

from utils.status_logic import (
    classify_quarter_status,
    classify_forecast_status,
    status_icon
)


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Project Dashboard",
    page_icon="📁",
    layout="wide"
)


# --------------------------------------------------
# SIMPLE PROFESSIONAL STYLE
# --------------------------------------------------

st.markdown(
    """
    <style>
    .page-title {
        color: #1F4E78;
        font-size: 2.1rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }

    .page-subtitle {
        color: #64748B;
        font-size: 1rem;
        margin-bottom: 1.3rem;
    }

    .summary-box {
        background-color: #F6F9FC;
        border-left: 5px solid #1F4E78;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }

    .insight-box {
        background-color: #F6F9FC;
        border-left: 5px solid #4472C4;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


st.markdown(
    '<div class="page-title">Project Performance Dashboard</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="page-subtitle">'
    'Quarterly, annual, and life-of-project monitoring'
    '</div>',
    unsafe_allow_html=True
)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

try:
    data, selected_sheet, available_sheets = load_dashboard_data()

except Exception as error:
    st.error("The monitoring dataset could not be loaded.")
    st.exception(error)
    st.stop()


data = prepare_numeric_columns(data)


required_columns = [
    "IndicatorID",
    "Project",
    "IndicatorName",
    "Year",
    "Quarter",
    "PeriodIndex",
    "QuarterTarget",
    "QuarterActual"
]


missing_columns = [
    column
    for column in required_columns
    if column not in data.columns
]


if missing_columns:
    st.error(
        "Required columns are missing: "
        + ", ".join(missing_columns)
    )
    st.stop()


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.header("Project Filters")

st.sidebar.caption(
    "Leave a filter empty to include all values."
)

available_projects = sorted(
    data["Project"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

available_years = sorted(
    data["Year"]
    .dropna()
    .astype(int)
    .unique()
    .tolist()
)

available_quarters = sorted(
    data["Quarter"]
    .dropna()
    .astype(int)
    .unique()
    .tolist()
)

selected_projects = st.sidebar.multiselect(
    "Projects",
    available_projects,
    default=[]
)

selected_years = st.sidebar.multiselect(
    "Years",
    available_years,
    default=[]
)

selected_quarters = st.sidebar.multiselect(
    "Quarters",
    available_quarters,
    default=[]
)

filtered_data = data.copy()

if selected_projects:

    filtered_data = filtered_data[
        filtered_data["Project"]
        .astype(str)
        .isin(selected_projects)
    ]

if selected_years:

    filtered_data = filtered_data[
        filtered_data["Year"]
        .astype(int)
        .isin(selected_years)
    ]

if selected_quarters:

    filtered_data = filtered_data[
        filtered_data["Quarter"]
        .astype(int)
        .isin(selected_quarters)
    ]

if filtered_data.empty:

    st.warning(
        "No data matches the selected filters."
    )

    st.stop()

# Backward compatibility with the rest of dashboard

project_data = filtered_data.copy()

selected_project = (
    "All Projects"
    if not selected_projects
    else ", ".join(selected_projects)
)

selected_year = (
    "All Years"
    if not selected_years
    else ", ".join(
        map(str, selected_years)
    )
)

selected_quarter = (
    "All Quarters"
    if not selected_quarters
    else ", ".join(
        [f"Q{q}" for q in selected_quarters]
    )
)

selected_period = None

# --------------------------------------------------
# CREATE PROJECT SNAPSHOT
# --------------------------------------------------

project_snapshot = (
    filtered_data
    .sort_values(
        ["IndicatorID", "PeriodIndex"]
    )
    .groupby(
        "IndicatorID",
        as_index=False
    )
    .tail(1)
    .reset_index(drop=True)
)


project_snapshot = filtered_data[
    filtered_data["Project"] == selected_project
].copy()


if project_snapshot.empty:
    st.warning(
        "No data are available for the selected "
        "project and reporting period."
    )
    st.stop()


# Recalculate status fields consistently

project_snapshot["QuarterStatus"] = (
    project_snapshot.apply(
        classify_quarter_status,
        axis=1
    )
)


if "AnnualForecastRatio" in project_snapshot.columns:
    project_snapshot["AnnualStatus"] = (
        project_snapshot["AnnualForecastRatio"]
        .apply(classify_forecast_status)
    )
else:
    project_snapshot["AnnualStatus"] = "No Data"


if "LoPForecastRatio" in project_snapshot.columns:
    project_snapshot["LoPStatus"] = (
        project_snapshot["LoPForecastRatio"]
        .apply(classify_forecast_status)
    )
else:
    project_snapshot["LoPStatus"] = "No Data"


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def status_count(column_name, status_name):

    if column_name not in project_snapshot.columns:
        return 0

    return int(
        project_snapshot[column_name]
        .eq(status_name)
        .sum()
    )


def safe_percentage(value):

    if pd.isna(value):
        return "No Data"

    return f"{value * 100:,.1f}%"


def project_overall_status(dataframe):

    valid = dataframe[
        dataframe["LoPStatus"].isin(
            ["On Track", "At Risk", "Off Track"]
        )
    ].copy()

    if valid.empty:
        return "No Data"

    off_track_share = (
        valid["LoPStatus"].eq("Off Track").mean()
    )

    concern_share = (
        valid["LoPStatus"]
        .isin(["At Risk", "Off Track"])
        .mean()
    )

    if off_track_share >= 0.30:
        return "Off Track"

    if concern_share >= 0.30:
        return "At Risk"

    return "On Track"


def dataframe_to_excel(dataframe):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Project_Snapshot",
            index=False
        )

    output.seek(0)

    return output.getvalue()


# --------------------------------------------------
# PROJECT PROFILE
# --------------------------------------------------

indicator_count = int(
    project_snapshot["IndicatorID"].nunique()
)


project_duration = int(
    project_data["Year"].dropna().max()
)


overall_status = project_overall_status(
    project_snapshot
)


st.markdown(
    f"""
    <div class="summary-box">
    <strong>Project:</strong> {selected_project}<br>
    <strong>Reporting period:</strong>
    Year {selected_year}, Quarter {selected_quarter}<br>
    <strong>Project duration represented:</strong>
    {project_duration} year(s)<br>
    <strong>Overall LoP monitoring signal:</strong>
    {status_icon(overall_status)} {overall_status}
    </div>
    """,
    unsafe_allow_html=True
)


profile1, profile2, profile3, profile4 = st.columns(4)


profile1.metric(
    "Project",
    selected_project
)


profile2.metric(
    "Reporting Period",
    f"Y{selected_year}Q{selected_quarter}"
)


profile3.metric(
    "Indicators",
    f"{indicator_count:,}"
)


profile4.metric(
    "Overall LoP Status",
    f"{status_icon(overall_status)} {overall_status}"
)


# --------------------------------------------------
# THREE-HORIZON STATUS SUMMARY
# --------------------------------------------------

st.divider()

st.subheader("Project Risk Summary")


quarter_counts = {
    "On Track": status_count(
        "QuarterStatus",
        "On Track"
    ),
    "At Risk": status_count(
        "QuarterStatus",
        "At Risk"
    ),
    "Off Track": status_count(
        "QuarterStatus",
        "Off Track"
    ),
    "Not Scheduled": status_count(
        "QuarterStatus",
        "Not Scheduled"
    )
}


annual_counts = {
    "On Track": status_count(
        "AnnualStatus",
        "On Track"
    ),
    "At Risk": status_count(
        "AnnualStatus",
        "At Risk"
    ),
    "Off Track": status_count(
        "AnnualStatus",
        "Off Track"
    )
}


lop_counts = {
    "On Track": status_count(
        "LoPStatus",
        "On Track"
    ),
    "At Risk": status_count(
        "LoPStatus",
        "At Risk"
    ),
    "Off Track": status_count(
        "LoPStatus",
        "Off Track"
    )
}


short_column, annual_column, lop_column = st.columns(3)


with short_column:

    st.markdown("### Short-Term")

    st.metric(
        "🟢 On Track",
        quarter_counts["On Track"]
    )

    st.metric(
        "🟡 At Risk",
        quarter_counts["At Risk"]
    )

    st.metric(
        "🔴 Off Track",
        quarter_counts["Off Track"]
    )

    st.caption(
        "⚪ Not Scheduled: "
        + str(quarter_counts["Not Scheduled"])
    )


with annual_column:

    st.markdown("### Annual")

    st.metric(
        "🟢 On Track",
        annual_counts["On Track"]
    )

    st.metric(
        "🟡 At Risk",
        annual_counts["At Risk"]
    )

    st.metric(
        "🔴 Off Track",
        annual_counts["Off Track"]
    )

    if "AnnualForecastRatio" in project_snapshot.columns:

        median_annual_ratio = (
            project_snapshot["AnnualForecastRatio"]
            .dropna()
            .median()
        )

        st.caption(
            "Median annual forecast: "
            + safe_percentage(
                median_annual_ratio
            )
        )


with lop_column:

    st.markdown("### Life of Project")

    st.metric(
        "🟢 On Track",
        lop_counts["On Track"]
    )

    st.metric(
        "🟡 At Risk",
        lop_counts["At Risk"]
    )

    st.metric(
        "🔴 Off Track",
        lop_counts["Off Track"]
    )

    if "LoPForecastRatio" in project_snapshot.columns:

        median_lop_ratio = (
            project_snapshot["LoPForecastRatio"]
            .dropna()
            .median()
        )

        st.caption(
            "Median LoP forecast: "
            + safe_percentage(
                median_lop_ratio
            )
        )


# --------------------------------------------------
# STATUS DISTRIBUTION CHARTS
# --------------------------------------------------

st.divider()

chart1, chart2 = st.columns(2)


status_colors = {
    "On Track": "#2E7D32",
    "At Risk": "#F9A825",
    "Off Track": "#C62828",
    "Not Scheduled": "#9E9E9E",
    "No Data": "#BDBDBD"
}


with chart1:

    st.subheader("Quarter Status Distribution")

    quarter_distribution = (
        project_snapshot["QuarterStatus"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Indicators")
    )

    quarter_chart = px.bar(
        quarter_distribution,
        x="Status",
        y="Indicators",
        color="Status",
        color_discrete_map=status_colors,
        text="Indicators"
    )

    quarter_chart.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Indicators",
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20
        )
    )

    st.plotly_chart(
        quarter_chart,
        use_container_width=True
    )


with chart2:

    st.subheader("LoP Status Distribution")

    lop_distribution = (
        project_snapshot["LoPStatus"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Indicators")
    )

    lop_chart = px.pie(
        lop_distribution,
        names="Status",
        values="Indicators",
        hole=0.55,
        color="Status",
        color_discrete_map=status_colors
    )

    lop_chart.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20
        )
    )

    st.plotly_chart(
        lop_chart,
        use_container_width=True
    )


# --------------------------------------------------
# PROJECT TREND
# --------------------------------------------------

st.divider()

st.subheader("Project Achievement Trend")


project_history = project_data[
    project_data["PeriodIndex"] <= selected_period
].copy()


scheduled_history = project_history[
    project_history["QuarterTarget"].notna()
    & project_history["QuarterActual"].notna()
    & project_history["QuarterTarget"].ne(0)
].copy()


if not scheduled_history.empty:

    scheduled_history["CalculatedRatio"] = (
        scheduled_history["QuarterActual"]
        / scheduled_history["QuarterTarget"]
    )

    project_trend = (
        scheduled_history
        .groupby(
            ["PeriodIndex", "PeriodLabel"],
            as_index=False
        )
        .agg(
            MedianAchievementRatio=(
                "CalculatedRatio",
                "median"
            ),
            IndicatorsReported=(
                "IndicatorID",
                "nunique"
            )
        )
        .sort_values("PeriodIndex")
    )

    project_trend["TargetReference"] = 1.0

    trend_chart = go.Figure()

    trend_chart.add_trace(
        go.Scatter(
            x=project_trend["PeriodLabel"],
            y=project_trend[
                "MedianAchievementRatio"
            ],
            mode="lines+markers",
            name="Median Achievement",
            line=dict(
                color="#1F77B4",
                width=3
            )
        )
    )

    trend_chart.add_trace(
        go.Scatter(
            x=project_trend["PeriodLabel"],
            y=project_trend["TargetReference"],
            mode="lines",
            name="Target Reference",
            line=dict(
                color="#2E7D32",
                width=2,
                dash="dash"
            )
        )
    )

    trend_chart.update_layout(
        xaxis_title="Reporting Period",
        yaxis_title="Median Achievement Ratio",
        hovermode="x unified",
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20
        )
    )

    trend_chart.update_yaxes(
        tickformat=".0%"
    )

    st.plotly_chart(
        trend_chart,
        use_container_width=True
    )

    st.caption(
        "The project trend uses the median achievement "
        "ratio because project indicators have different "
        "units and should not be added together."
    )

else:

    st.info(
        "No scheduled quarterly observations are "
        "available for the selected reporting period."
    )


# --------------------------------------------------
# PROGRESS GAP REVIEW
# --------------------------------------------------

st.divider()

st.subheader("Indicators with the Largest Progress Gaps")


gap_column1, gap_column2 = st.columns(2)


with gap_column1:

    st.markdown("#### Annual Progress Gap")

    if "AnnualProgressGap" in project_snapshot.columns:

        annual_gap_data = (
            project_snapshot[
                [
                    "IndicatorName",
                    "AnnualProgressGap"
                ]
            ]
            .dropna(
                subset=["AnnualProgressGap"]
            )
            .sort_values("AnnualProgressGap")
            .head(12)
        )

        if not annual_gap_data.empty:

            annual_gap_chart = px.bar(
                annual_gap_data,
                x="AnnualProgressGap",
                y="IndicatorName",
                orientation="h",
                color="AnnualProgressGap",
                color_continuous_scale=[
                    "#C62828",
                    "#F9A825",
                    "#2E7D32"
                ]
            )

            annual_gap_chart.update_layout(
                coloraxis_showscale=False,
                xaxis_tickformat=".0%",
                xaxis_title="Annual Progress Gap",
                yaxis_title="",
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20
                )
            )

            st.plotly_chart(
                annual_gap_chart,
                use_container_width=True
            )

        else:

            st.info(
                "Annual progress-gap values are unavailable."
            )


with gap_column2:

    st.markdown("#### LoP Progress Gap")

    if "LoPProgressGap" in project_snapshot.columns:

        lop_gap_data = (
            project_snapshot[
                [
                    "IndicatorName",
                    "LoPProgressGap"
                ]
            ]
            .dropna(
                subset=["LoPProgressGap"]
            )
            .sort_values("LoPProgressGap")
            .head(12)
        )

        if not lop_gap_data.empty:

            lop_gap_chart = px.bar(
                lop_gap_data,
                x="LoPProgressGap",
                y="IndicatorName",
                orientation="h",
                color="LoPProgressGap",
                color_continuous_scale=[
                    "#C62828",
                    "#F9A825",
                    "#2E7D32"
                ]
            )

            lop_gap_chart.update_layout(
                coloraxis_showscale=False,
                xaxis_tickformat=".0%",
                xaxis_title="LoP Progress Gap",
                yaxis_title="",
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20
                )
            )

            st.plotly_chart(
                lop_gap_chart,
                use_container_width=True
            )

        else:

            st.info(
                "LoP progress-gap values are unavailable."
            )


# --------------------------------------------------
# PRIORITY INDICATORS
# --------------------------------------------------

st.divider()

st.subheader("Indicators Requiring Priority Attention")


priority_indicators = project_snapshot[
    project_snapshot["LoPStatus"].isin(
        ["Off Track", "At Risk"]
    )
].copy()


if not priority_indicators.empty:

    priority_indicators["PriorityOrder"] = (
        priority_indicators["LoPStatus"]
        .map(
            {
                "Off Track": 1,
                "At Risk": 2
            }
        )
    )

    sort_columns = ["PriorityOrder"]

    if "LoPForecastRatio" in priority_indicators.columns:
        sort_columns.append("LoPForecastRatio")

    priority_indicators = (
        priority_indicators
        .sort_values(
            sort_columns,
            ascending=True
        )
    )

    display_columns = [
        column
        for column in [
            "IndicatorID",
            "IndicatorName",
            "PeriodLabel",
            "QuarterStatus",
            "AnnualStatus",
            "LoPStatus",
            "AnnualForecastRatio",
            "AnnualProgressGap",
            "LoPForecastRatio",
            "LoPProgressGap"
        ]
        if column in priority_indicators.columns
    ]

    st.dataframe(
        priority_indicators[
            display_columns
        ].head(25),
        hide_index=True,
        use_container_width=True
    )

else:

    st.success(
        "No indicators are classified as At Risk "
        "or Off Track for the selected period."
    )


# --------------------------------------------------
# MANAGEMENT INTERPRETATION
# --------------------------------------------------

st.divider()

st.subheader("Management Interpretation")


valid_lop_total = (
    lop_counts["On Track"]
    + lop_counts["At Risk"]
    + lop_counts["Off Track"]
)


if valid_lop_total > 0:

    concern_share = (
        lop_counts["At Risk"]
        + lop_counts["Off Track"]
    ) / valid_lop_total

    off_track_share = (
        lop_counts["Off Track"]
        / valid_lop_total
    )

else:

    concern_share = np.nan
    off_track_share = np.nan


if overall_status == "Off Track":

    interpretation = (
        "The project is classified as Off Track on "
        "the LoP monitoring horizon. "
        f"{off_track_share * 100:,.1f}% of indicators "
        "with available classifications are Off Track. "
        "Review the priority indicators, implementation "
        "pace, reporting quality, and feasible corrective "
        "actions."
    )

elif overall_status == "At Risk":

    interpretation = (
        "The project requires close monitoring. "
        f"{concern_share * 100:,.1f}% of indicators "
        "with available LoP classifications are At Risk "
        "or Off Track. Review the indicators with the "
        "largest negative annual and LoP progress gaps."
    )

elif overall_status == "On Track":

    interpretation = (
        "The majority of indicators with available LoP "
        "classifications are currently On Track. Continue "
        "routine monitoring and review individual At Risk "
        "or Off Track indicators."
    )

else:

    interpretation = (
        "There is insufficient information to classify "
        "overall project performance."
    )


st.markdown(
    f"""
    <div class="insight-box">
    <strong>Project-level insight</strong><br>
    {interpretation}
    </div>
    """,
    unsafe_allow_html=True
)


st.warning(
    "The project classification is a decision-support "
    "signal. MEL and program staff should review indicator "
    "definitions, reporting schedules, data quality, and "
    "implementation context before management action."
)


# --------------------------------------------------
# DOWNLOAD SNAPSHOT
# --------------------------------------------------

st.divider()

st.subheader("Download Project Snapshot")


download_columns = [
    column
    for column in [
        "Project",
        "IndicatorID",
        "IndicatorName",
        "Year",
        "Quarter",
        "PeriodLabel",
        "QuarterTarget",
        "QuarterActual",
        "AchievementRatio",
        "QuarterStatus",
        "AnnualTarget",
        "CurrentYearActual",
        "AnnualForecastRatio",
        "AnnualProgressGap",
        "AnnualStatus",
        "LoPTarget",
        "CumulativeActual",
        "LoPForecastRatio",
        "LoPProgressGap",
        "LoPStatus"
    ]
    if column in project_snapshot.columns
]


download_data = project_snapshot[
    download_columns
].copy()


download_filename = (
    selected_project.replace(" ", "_")
    + f"_Y{selected_year}Q{selected_quarter}"
    + "_Project_Snapshot.xlsx"
)


st.download_button(
    label="Download project monitoring snapshot",
    data=dataframe_to_excel(download_data),
    file_name=download_filename,
    mime=(
        "application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet"
    )
)


st.caption(
    f"Data source sheet: {selected_sheet}. "
    "The snapshot uses the latest available observation "
    "for each indicator up to the selected reporting period."
)

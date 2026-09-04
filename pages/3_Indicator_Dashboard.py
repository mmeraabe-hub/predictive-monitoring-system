%%writefile pages/3_Indicator_Dashboard.py
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_utils import (
    load_dashboard_data,
    prepare_numeric_columns,
)

from utils.risk_thresholds import classify_risk


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Indicator Dashboard",
    page_icon="🎯",
    layout="wide",
)


# ==================================================
# PROFESSIONAL STYLE
# ==================================================

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
        margin-bottom: 1.2rem;
    }

    .monitoring-card {
        background-color: #F7FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }

    .insight-card {
        background-color: #F6F9FC;
        border-left: 5px solid #1F4E78;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
    }

    .method-note {
        background-color: #FFF8E1;
        border-left: 5px solid #F9A825;
        border-radius: 8px;
        padding: 0.9rem;
        margin-top: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="page-title">'
    'Indicator Performance Dashboard'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="page-subtitle">'
    'Detailed quarterly, annual, and life-of-project monitoring'
    '</div>',
    unsafe_allow_html=True,
)


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def safe_percentage(value):

    if pd.isna(value):
        return "No Data"

    return f"{float(value):.1%}"


def safe_number(value):

    if pd.isna(value):
        return "No Data"

    return f"{float(value):,.1f}"


def safe_classify(value, assessment_level):

    if pd.isna(value):
        return "Unknown"

    return classify_risk(
        float(value),
        assessment_level,
    )


def status_icon(status):

    icons = {
        "On Track": "🟢",
        "At Risk": "🟡",
        "Off Track": "🔴",
        "Unknown": "⚪",
    }

    return icons.get(status, "⚪")


def dataframe_to_excel(dataframe):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Indicator_Data",
            index=False,
        )

    output.seek(0)

    return output.getvalue()


# ==================================================
# LOAD DATA
# ==================================================

try:

    data, selected_sheet, available_sheets = (
        load_dashboard_data()
    )

except Exception as error:

    st.error(
        "The monitoring dataset could not be loaded."
    )

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
    "PeriodLabel",
    "QuarterTarget",
    "QuarterActual",
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


# ==================================================
# OPTIONAL MULTISELECT FILTERS
# ==================================================

st.sidebar.header("Indicator Filters")

st.sidebar.caption(
    "Leave project, year, and quarter filters empty "
    "to include all available values."
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
    options=available_projects,
    default=[],
    placeholder="All projects",
)


selected_years = st.sidebar.multiselect(
    "Years",
    options=available_years,
    default=[],
    placeholder="All years",
)


selected_quarters = st.sidebar.multiselect(
    "Quarters",
    options=available_quarters,
    default=[],
    placeholder="All quarters",
)


filtered_data = data.copy()


if selected_projects:

    filtered_data = filtered_data[
        filtered_data["Project"]
        .astype(str)
        .isin(selected_projects)
    ].copy()


if selected_years:

    filtered_data = filtered_data[
        filtered_data["Year"]
        .astype(int)
        .isin(selected_years)
    ].copy()


if selected_quarters:

    filtered_data = filtered_data[
        filtered_data["Quarter"]
        .astype(int)
        .isin(selected_quarters)
    ].copy()


if filtered_data.empty:

    st.warning(
        "No monitoring records match the selected "
        "project, year, and quarter filters."
    )

    st.stop()


# ==================================================
# INDICATOR MULTISELECT
# ==================================================

indicator_lookup = (
    filtered_data[
        [
            "IndicatorID",
            "IndicatorName",
        ]
    ]
    .drop_duplicates(
        subset=["IndicatorID"]
    )
    .sort_values(
        [
            "IndicatorName",
            "IndicatorID",
        ]
    )
)


indicator_label_to_id = {
    (
        str(row["IndicatorID"])
        + " | "
        + str(row["IndicatorName"])
    ): row["IndicatorID"]

    for _, row in indicator_lookup.iterrows()
}


selected_indicator_labels = st.sidebar.multiselect(
    "Indicators",
    options=list(
        indicator_label_to_id.keys()
    ),
    default=[],
    placeholder="Select indicators",
)


# ==================================================
# FILTER-SCOPE SUMMARY
# ==================================================

project_scope_label = (
    "All Projects"
    if not selected_projects
    else ", ".join(selected_projects)
)


year_scope_label = (
    "All Years"
    if not selected_years
    else ", ".join(
        str(year)
        for year in selected_years
    )
)


quarter_scope_label = (
    "All Quarters"
    if not selected_quarters
    else ", ".join(
        f"Q{quarter}"
        for quarter in selected_quarters
    )
)


indicator_scope_label = (
    "No detailed indicator selected"
    if not selected_indicator_labels
    else (
        f"{len(selected_indicator_labels)} "
        "indicator(s) selected"
    )
)


st.info(
    f"Projects: {project_scope_label} | "
    f"Years: {year_scope_label} | "
    f"Quarters: {quarter_scope_label} | "
    f"Indicators: {indicator_scope_label} | "
    f"Source sheet: {selected_sheet}"
)


# ==================================================
# REQUIRE INDICATOR SELECTION FOR DETAILED ANALYSIS
# ==================================================

if not selected_indicator_labels:

    st.subheader(
        "Select Indicators for Detailed Analysis"
    )

    st.info(
        "Use the Indicators filter in the sidebar to select "
        "one or more indicators. Project, year, and quarter "
        "filters may remain empty to include all available data."
    )

    available_indicator_summary = (
        filtered_data[
            [
                "Project",
                "IndicatorID",
                "IndicatorName",
                "Unit",
            ]
        ]
        .drop_duplicates(
            subset=["IndicatorID"]
        )
        .sort_values(
            [
                "Project",
                "IndicatorName",
            ]
        )
    )


    st.dataframe(
        available_indicator_summary,
        hide_index=True,
        use_container_width=True,
    )


    st.caption(
        f"{len(available_indicator_summary):,} indicators "
        "are available under the current project, year, "
        "and quarter filter scope."
    )

    st.stop()


selected_indicator_ids = [
    indicator_label_to_id[label]
    for label in selected_indicator_labels
]


indicator_data = filtered_data[
    filtered_data["IndicatorID"]
    .isin(selected_indicator_ids)
].copy()


indicator_data = indicator_data.sort_values(
    [
        "IndicatorID",
        "PeriodIndex",
    ]
).reset_index(drop=True)


if indicator_data.empty:

    st.warning(
        "No observations are available for the selected indicators."
    )

    st.stop()


# ==================================================
# LATEST RECORD FOR EACH SELECTED INDICATOR
# ==================================================

indicator_snapshot = (
    indicator_data
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


# ==================================================
# RECALCULATE CONSISTENT RISK STATUSES
# ==================================================

if "AchievementRatio" in indicator_snapshot.columns:

    indicator_snapshot["QuarterStatus"] = (
        indicator_snapshot["AchievementRatio"]
        .apply(
            lambda value: safe_classify(
                value,
                "Quarterly",
            )
        )
    )

else:

    indicator_snapshot["QuarterStatus"] = "Unknown"


if "AnnualForecastRatio" in indicator_snapshot.columns:

    indicator_snapshot["AnnualStatus"] = (
        indicator_snapshot["AnnualForecastRatio"]
        .apply(
            lambda value: safe_classify(
                value,
                "Annual",
            )
        )
    )

else:

    indicator_snapshot["AnnualStatus"] = "Unknown"


if "LoPForecastRatio" in indicator_snapshot.columns:

    indicator_snapshot["LoPStatus"] = (
        indicator_snapshot["LoPForecastRatio"]
        .apply(
            lambda value: safe_classify(
                value,
                "LoP",
            )
        )
    )

else:

    indicator_snapshot["LoPStatus"] = "Unknown"


# ==================================================
# INDICATOR PROFILE
# ==================================================

st.subheader("Indicator Overview")


profile1, profile2, profile3, profile4 = st.columns(4)


profile1.metric(
    "Selected Indicators",
    len(selected_indicator_ids),
)


profile2.metric(
    "Projects Represented",
    indicator_snapshot["Project"].nunique(),
)


profile3.metric(
    "Observations",
    len(indicator_data),
)


latest_period = (
    indicator_snapshot["PeriodLabel"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


profile4.metric(
    "Latest Matching Period",
    (
        ", ".join(latest_period[:3])
        if latest_period
        else "No Data"
    ),
)


# ==================================================
# LATEST STATUS SUMMARY
# ==================================================

st.divider()

st.subheader("Latest Indicator Status Summary")


quarter_on_track = int(
    indicator_snapshot["QuarterStatus"]
    .eq("On Track")
    .sum()
)

quarter_at_risk = int(
    indicator_snapshot["QuarterStatus"]
    .eq("At Risk")
    .sum()
)

quarter_off_track = int(
    indicator_snapshot["QuarterStatus"]
    .eq("Off Track")
    .sum()
)


annual_on_track = int(
    indicator_snapshot["AnnualStatus"]
    .eq("On Track")
    .sum()
)

annual_at_risk = int(
    indicator_snapshot["AnnualStatus"]
    .eq("At Risk")
    .sum()
)

annual_off_track = int(
    indicator_snapshot["AnnualStatus"]
    .eq("Off Track")
    .sum()
)


lop_on_track = int(
    indicator_snapshot["LoPStatus"]
    .eq("On Track")
    .sum()
)

lop_at_risk = int(
    indicator_snapshot["LoPStatus"]
    .eq("At Risk")
    .sum()
)

lop_off_track = int(
    indicator_snapshot["LoPStatus"]
    .eq("Off Track")
    .sum()
)


quarter_column, annual_column, lop_column = st.columns(3)


with quarter_column:

    st.markdown("### Quarterly")

    st.metric(
        "🟢 On Track",
        quarter_on_track,
    )

    st.metric(
        "🟡 At Risk",
        quarter_at_risk,
    )

    st.metric(
        "🔴 Off Track",
        quarter_off_track,
    )


with annual_column:

    st.markdown("### Annual Forecast")

    st.metric(
        "🟢 On Track",
        annual_on_track,
    )

    st.metric(
        "🟡 At Risk",
        annual_at_risk,
    )

    st.metric(
        "🔴 Off Track",
        annual_off_track,
    )


with lop_column:

    st.markdown("### LoP Forecast")

    st.metric(
        "🟢 On Track",
        lop_on_track,
    )

    st.metric(
        "🟡 At Risk",
        lop_at_risk,
    )

    st.metric(
        "🔴 Off Track",
        lop_off_track,
    )


# ==================================================
# CHART 1: QUARTERLY ACTUAL VS TARGET
# ==================================================

st.divider()

st.subheader(
    "1. Quarterly Actual vs Target Trend"
)


quarter_chart = go.Figure()


for indicator_id in selected_indicator_ids:

    one_indicator = indicator_data[
        indicator_data["IndicatorID"]
        == indicator_id
    ].copy()


    if one_indicator.empty:
        continue


    indicator_name_values = (
        one_indicator["IndicatorName"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


    indicator_name = (
        indicator_name_values[0]
        if indicator_name_values
        else str(indicator_id)
    )


    chart_label = (
        f"{indicator_id} | {indicator_name}"
    )


    quarter_chart.add_trace(
        go.Scatter(
            x=one_indicator["PeriodLabel"],
            y=one_indicator["QuarterActual"],
            mode="lines+markers",
            name=f"{chart_label} Actual",
            hovertemplate=(
                "%{x}<br>"
                "Actual: %{y:,.1f}"
                "<extra></extra>"
            ),
        )
    )


    quarter_chart.add_trace(
        go.Scatter(
            x=one_indicator["PeriodLabel"],
            y=one_indicator["QuarterTarget"],
            mode="lines+markers",
            name=f"{chart_label} Target",
            line=dict(
                dash="dash",
            ),
            hovertemplate=(
                "%{x}<br>"
                "Target: %{y:,.1f}"
                "<extra></extra>"
            ),
        )
    )


quarter_chart.update_layout(
    xaxis_title="Reporting Period",
    yaxis_title="Quarter Value",
    hovermode="x unified",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
    ),
    margin=dict(
        l=20,
        r=20,
        t=40,
        b=20,
    ),
)


st.plotly_chart(
    quarter_chart,
    use_container_width=True,
)


st.caption(
    "Solid lines show reported quarterly actual values. "
    "Dashed lines show quarterly target values."
)


# ==================================================
# CHART 2: ACHIEVEMENT RATIO TREND
# ==================================================

st.divider()

st.subheader(
    "2. Quarterly Achievement Ratio Trend"
)


achievement_chart = go.Figure()


for indicator_id in selected_indicator_ids:

    one_indicator = indicator_data[
        indicator_data["IndicatorID"]
        == indicator_id
    ].copy()


    if one_indicator.empty:
        continue


    if "AchievementRatio" not in one_indicator.columns:
        continue


    indicator_name_values = (
        one_indicator["IndicatorName"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


    indicator_name = (
        indicator_name_values[0]
        if indicator_name_values
        else str(indicator_id)
    )


    chart_label = (
        f"{indicator_id} | {indicator_name}"
    )


    achievement_chart.add_trace(
        go.Scatter(
            x=one_indicator["PeriodLabel"],
            y=one_indicator["AchievementRatio"],
            mode="lines+markers",
            name=chart_label,
            hovertemplate=(
                "%{x}<br>"
                "Achievement: %{y:.1%}"
                "<extra></extra>"
            ),
        )
    )


achievement_chart.add_hline(
    y=1.0,
    line_dash="dash",
    line_color="#2E7D32",
    annotation_text="Target reference: 100%",
)


achievement_chart.add_hline(
    y=0.90,
    line_dash="dot",
    line_color="#F9A825",
    annotation_text="Quarterly On Track threshold: 90%",
)


achievement_chart.add_hline(
    y=0.70,
    line_dash="dot",
    line_color="#C62828",
    annotation_text="Quarterly At Risk threshold: 70%",
)


achievement_chart.update_layout(
    xaxis_title="Reporting Period",
    yaxis_title="Achievement Ratio",
    hovermode="x unified",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
    ),
    margin=dict(
        l=20,
        r=20,
        t=40,
        b=20,
    ),
)


achievement_chart.update_yaxes(
    tickformat=".0%",
)


st.plotly_chart(
    achievement_chart,
    use_container_width=True,
)


st.caption(
    "The achievement ratio is calculated as Actual divided "
    "by Target. The horizontal lines show the target reference "
    "and centralized quarterly risk thresholds."
)


# ==================================================
# CHART 3: ANNUAL AND LOP FORECAST OUTLOOK
# ==================================================

st.divider()

st.subheader(
    "3. Annual and Life-of-Project Forecast Outlook"
)


forecast_chart = go.Figure()


if "AnnualForecastRatio" in indicator_snapshot.columns:

    forecast_chart.add_trace(
        go.Bar(
            x=indicator_snapshot[
                "IndicatorID"
            ].astype(str),
            y=indicator_snapshot[
                "AnnualForecastRatio"
            ],
            name="Annual Forecast",
            marker_color="#2563EB",
            customdata=indicator_snapshot[
                "IndicatorName"
            ],
            hovertemplate=(
                "Indicator: %{customdata}<br>"
                "Annual forecast: %{y:.1%}"
                "<extra></extra>"
            ),
        )
    )


if "LoPForecastRatio" in indicator_snapshot.columns:

    forecast_chart.add_trace(
        go.Bar(
            x=indicator_snapshot[
                "IndicatorID"
            ].astype(str),
            y=indicator_snapshot[
                "LoPForecastRatio"
            ],
            name="LoP Forecast",
            marker_color="#16A34A",
            customdata=indicator_snapshot[
                "IndicatorName"
            ],
            hovertemplate=(
                "Indicator: %{customdata}<br>"
                "LoP forecast: %{y:.1%}"
                "<extra></extra>"
            ),
        )
    )


forecast_chart.add_hline(
    y=1.0,
    line_dash="dash",
    line_color="#DC2626",
    annotation_text="Target: 100%",
)


forecast_chart.update_layout(
    barmode="group",
    xaxis_title="Indicator",
    yaxis_title="Forecast Achievement Index",
    hovermode="x unified",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
    ),
    margin=dict(
        l=20,
        r=20,
        t=40,
        b=20,
    ),
)


forecast_chart.update_yaxes(
    tickformat=".0%",
)


st.plotly_chart(
    forecast_chart,
    use_container_width=True,
)


st.caption(
    "Blue bars show the expected Annual achievement index. "
    "Green bars show the expected Life-of-Project achievement "
    "index. The red dashed line represents the 100% target."
)


# ==================================================
# LATEST INDICATOR TABLE
# ==================================================

st.divider()

st.subheader(
    "Latest Indicator Monitoring Snapshot"
)


snapshot_columns = [
    column
    for column in [
        "Project",
        "IndicatorID",
        "IndicatorName",
        "Unit",
        "Year",
        "Quarter",
        "PeriodLabel",
        "QuarterTarget",
        "QuarterActual",
        "AchievementRatio",
        "QuarterStatus",
        "AnnualTarget",
        "CurrentYearActual",
        "AnnualProgress",
        "AnnualForecastRatio",
        "AnnualStatus",
        "LoPTarget",
        "CumulativeActual",
        "LoPProgress",
        "LoPForecastRatio",
        "LoPStatus",
    ]
    if column in indicator_snapshot.columns
]


snapshot_display = indicator_snapshot[
    snapshot_columns
].copy()


percentage_columns = [
    "AchievementRatio",
    "AnnualProgress",
    "AnnualForecastRatio",
    "LoPProgress",
    "LoPForecastRatio",
]


for column in percentage_columns:

    if column in snapshot_display.columns:

        snapshot_display[
            f"{column} (%)"
        ] = (
            snapshot_display[column] * 100
        ).round(1)

        snapshot_display = (
            snapshot_display.drop(
                columns=[column]
            )
        )


st.dataframe(
    snapshot_display,
    hide_index=True,
    use_container_width=True,
)


# ==================================================
# MANAGEMENT INTERPRETATION
# ==================================================

st.divider()

st.subheader(
    "Management Interpretation"
)


total_selected = len(
    indicator_snapshot
)


forecast_concern_count = int(
    indicator_snapshot["LoPStatus"]
    .isin(
        [
            "At Risk",
            "Off Track",
        ]
    )
    .sum()
)


if total_selected > 0:

    concern_share = (
        forecast_concern_count
        / total_selected
    )

else:

    concern_share = np.nan


if forecast_concern_count == 0:

    indicator_interpretation = (
        "None of the selected indicators are currently "
        "classified as At Risk or Off Track under the "
        "Life-of-Project forecast."
    )

elif concern_share >= 0.50:

    indicator_interpretation = (
        f"{concern_share:.1%} of the selected indicators "
        "are forecasted as At Risk or Off Track at the "
        "Life-of-Project level. Program and MEL teams should "
        "review the underlying data, implementation context, "
        "and feasible corrective actions."
    )

else:

    indicator_interpretation = (
        f"{concern_share:.1%} of the selected indicators "
        "are forecasted as At Risk or Off Track at the "
        "Life-of-Project level. These indicators should be "
        "closely monitored while implementation continues."
    )


st.markdown(
    f"""
    <div class="insight-card">
    <strong>Indicator-level insight</strong><br>
    {indicator_interpretation}
    </div>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="method-note">
    <strong>Interpretation note</strong><br>
    Forecasts and risk classifications are decision-support
    signals. Program and MEL staff should also review indicator
    definitions, data quality, reporting schedules, external
    factors, and implementation context before management action.
    </div>
    """,
    unsafe_allow_html=True,
)


# ==================================================
# DOWNLOAD FILTERED INDICATOR DATA
# ==================================================

st.divider()

st.subheader(
    "Download Indicator Data"
)


safe_indicator_name = (
    "Selected_Indicators"
    if len(selected_indicator_ids) > 1
    else str(
        selected_indicator_ids[0]
    ).replace(
        " ",
        "_",
    )
)


safe_project_name = (
    "All_Projects"
    if not selected_projects
    else "_".join(
        project.replace(
            " ",
            "_",
        )
        for project in selected_projects
    )
)


safe_year_name = (
    "All_Years"
    if not selected_years
    else "_".join(
        f"Y{year}"
        for year in selected_years
    )
)


safe_quarter_name = (
    "All_Quarters"
    if not selected_quarters
    else "_".join(
        f"Q{quarter}"
        for quarter in selected_quarters
    )
)


download_filename = (
    f"{safe_project_name}_"
    f"{safe_indicator_name}_"
    f"{safe_year_name}_"
    f"{safe_quarter_name}_"
    "Indicator_Data.xlsx"
)


st.download_button(
    label="Download filtered indicator data",
    data=dataframe_to_excel(
        indicator_data
    ),
    file_name=download_filename,
    mime=(
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
)


st.caption(
    f"Data source sheet: {selected_sheet}. "
    "The download contains all matching observations for "
    "the selected indicators after applying the optional filters."
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

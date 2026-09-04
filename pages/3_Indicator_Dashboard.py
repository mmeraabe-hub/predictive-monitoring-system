
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_utils import (
    load_dashboard_data,
    prepare_numeric_columns,
    get_indicator_history
)

from utils.status_logic import (
    classify_quarter_status,
    classify_forecast_status,
    status_icon
)


# --------------------------------------------------
# PAGE SETUP
# --------------------------------------------------

st.set_page_config(
    page_title="Indicator Dashboard",
    page_icon="🎯",
    layout="wide"
)


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
    unsafe_allow_html=True
)


st.markdown(
    '<div class="page-title">'
    'Indicator Performance Dashboard'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="page-subtitle">'
    'Detailed quarterly, annual, and life-of-project monitoring'
    '</div>',
    unsafe_allow_html=True
)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

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

st.sidebar.header("Indicator Selection")

projects = sorted(
    data["Project"]
    .dropna()
    .astype(str)
    .unique()
)

selected_project = st.sidebar.selectbox(
    "Project",
    projects
)

project_data = data[
    data["Project"] == selected_project
].copy()

indicator_lookup = (
    project_data[
        [
            "IndicatorID",
            "IndicatorName"
        ]
    ]
    .drop_duplicates()
    .sort_values("IndicatorName")
)

indicator_labels = {
    (
        str(row["IndicatorID"])
        + " | "
        + str(row["IndicatorName"])
    ): row["IndicatorID"]

    for _, row in indicator_lookup.iterrows()
}

selected_indicator_label = st.sidebar.selectbox(
    "Indicator",
    list(indicator_labels.keys())
)

selected_indicator_id = indicator_labels[
    selected_indicator_label
]

indicator_data = project_data[
    project_data["IndicatorID"]
    == selected_indicator_id
].copy()

available_years = sorted(
    indicator_data["Year"]
    .dropna()
    .astype(int)
    .unique()
)

selected_year = st.sidebar.selectbox(
    "Reporting Year",
    available_years,
    index=len(available_years) - 1
)

available_quarters = sorted(
    indicator_data.loc[
        indicator_data["Year"]
        == selected_year,
        "Quarter"
    ]
    .dropna()
    .astype(int)
    .unique()
)

if not available_quarters:
    available_quarters = [1, 2, 3, 4]

selected_quarter = st.sidebar.selectbox(
    "Reporting Quarter",
    available_quarters,
    index=len(available_quarters) - 1
)

selected_period = (
    ((int(selected_year) - 1) * 4)
    + int(selected_quarter)
)

history = get_indicator_history(
    data=data,
    indicator_id=selected_indicator_id,
    selected_period=selected_period
)

if history.empty:

    st.warning(
        "No observations are available for the selected "
        "indicator and reporting period."
    )

    st.stop()

current_record = history.iloc[-1]


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def safe_number(value, decimals=1):

    if pd.isna(value):
        return "No Data"

    return f"{value:,.{decimals}f}"


def safe_percentage(value):

    if pd.isna(value):
        return "No Data"

    return f"{value * 100:,.1f}%"


def progress_bar(value, label):

    st.write(label)

    if pd.isna(value):

        st.caption("No data available.")
        return

    displayed_value = min(
        max(float(value), 0.0),
        1.0
    )

    st.progress(displayed_value)

    st.caption(
        safe_percentage(value)
    )


def gap_text(value, horizon):

    if pd.isna(value):

        return (
            f"{horizon} progress gap cannot "
            "be calculated."
        )

    gap_percent = abs(value * 100)

    if value > 0.02:

        return (
            f"{horizon} progress is "
            f"{gap_percent:,.1f}% ahead of the "
            "expected time-based trajectory."
        )

    if value < -0.02:

        return (
            f"{horizon} progress is "
            f"{gap_percent:,.1f}% behind the "
            "expected time-based trajectory."
        )

    return (
        f"{horizon} progress is broadly aligned "
        "with the expected time-based trajectory."
    )


def dataframe_to_excel(dataframe):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Indicator_History",
            index=False
        )

    output.seek(0)

    return output.getvalue()


# --------------------------------------------------
# CURRENT STATUS
# --------------------------------------------------

quarter_status = classify_quarter_status(
    current_record
)


annual_ratio = current_record.get(
    "AnnualForecastRatio",
    np.nan
)


lop_ratio = current_record.get(
    "LoPForecastRatio",
    np.nan
)


annual_status = classify_forecast_status(
    annual_ratio
)


lop_status = classify_forecast_status(
    lop_ratio
)


# --------------------------------------------------
# INDICATOR PROFILE
# --------------------------------------------------

st.subheader("Indicator Profile")


profile1, profile2, profile3, profile4 = (
    st.columns(4)
)


profile1.metric(
    "Project",
    selected_project
)


profile2.metric(
    "Reporting Period",
    f"Y{selected_year}Q{selected_quarter}"
)


profile3.metric(
    "Unit",
    str(
        current_record.get(
            "Unit",
            "Not specified"
        )
    )
)


profile4.metric(
    "LoP Target",
    safe_number(
        current_record.get(
            "LoPTarget",
            np.nan
        )
    )
)


st.markdown(
    "**Indicator:** "
    + str(current_record["IndicatorName"])
)


baseline = current_record.get(
    "Baseline",
    np.nan
)


if not pd.isna(baseline):

    st.caption(
        "Baseline: "
        + safe_number(
            baseline,
            decimals=2
        )
    )


# --------------------------------------------------
# THREE MONITORING HORIZONS
# --------------------------------------------------

st.divider()

st.subheader("Monitoring Summary")


quarter_column, annual_column, lop_column = (
    st.columns(3)
)


with quarter_column:

    st.markdown("### Short-Term")

    st.markdown(
        f"## {status_icon(quarter_status)} "
        f"{quarter_status}"
    )

    quarter_target = current_record.get(
        "QuarterTarget",
        np.nan
    )

    quarter_actual = current_record.get(
        "QuarterActual",
        np.nan
    )

    quarter_ratio = current_record.get(
        "AchievementRatio",
        np.nan
    )

    st.metric(
        "Quarter Target",
        safe_number(quarter_target)
    )

    st.metric(
        "Quarter Actual",
        safe_number(quarter_actual)
    )

    st.metric(
        "Quarter Achievement",
        safe_percentage(quarter_ratio)
    )

    if quarter_status == "Not Scheduled":

        st.info(
            "No target was scheduled for this quarter."
        )

    else:

        progress_bar(
            quarter_ratio,
            "Quarter progress"
        )


with annual_column:

    st.markdown("### Medium-Term")

    st.markdown(
        f"## {status_icon(annual_status)} "
        f"{annual_status}"
    )

    annual_target = current_record.get(
        "AnnualTarget",
        np.nan
    )

    current_year_actual = current_record.get(
        "CurrentYearActual",
        np.nan
    )

    annual_progress = current_record.get(
        "AnnualProgress",
        np.nan
    )

    annual_gap = current_record.get(
        "AnnualProgressGap",
        np.nan
    )

    st.metric(
        "Annual Target",
        safe_number(annual_target)
    )

    st.metric(
        "Current Year Actual",
        safe_number(current_year_actual)
    )

    st.metric(
        "Annual Forecast Index",
        safe_percentage(annual_ratio),
        delta=(
            None
            if pd.isna(annual_gap)
            else f"{annual_gap * 100:+.1f}% gap"
        )
    )

    progress_bar(
        annual_ratio,
        "Pace-based annual forecast"
    )

    st.caption(
        gap_text(
            annual_gap,
            "Annual"
        )
    )


with lop_column:

    st.markdown("### Long-Term")

    st.markdown(
        f"## {status_icon(lop_status)} "
        f"{lop_status}"
    )

    lop_target = current_record.get(
        "LoPTarget",
        np.nan
    )

    cumulative_actual = current_record.get(
        "CumulativeActual",
        np.nan
    )

    lop_progress = current_record.get(
        "LoPProgress",
        np.nan
    )

    lop_gap = current_record.get(
        "LoPProgressGap",
        np.nan
    )

    st.metric(
        "LoP Target",
        safe_number(lop_target)
    )

    st.metric(
        "Cumulative Actual",
        safe_number(cumulative_actual)
    )

    st.metric(
        "LoP Forecast Index",
        safe_percentage(lop_ratio),
        delta=(
            None
            if pd.isna(lop_gap)
            else f"{lop_gap * 100:+.1f}% gap"
        )
    )

    progress_bar(
        lop_ratio,
        "Pace-based LoP forecast"
    )

    st.caption(
        gap_text(
            lop_gap,
            "LoP"
        )
    )


# --------------------------------------------------
# ACTUAL, TARGET, AND FORECAST TREND
# --------------------------------------------------

# --------------------------------------------------
# PERFORMANCE TREND ANALYSIS
# --------------------------------------------------

st.divider()

st.subheader(
    "Performance Trend Analysis"
)

history_trend = (
    history
    .sort_values("PeriodIndex")
    .copy()
)

# ==================================
# CHART 1
# ==================================

st.markdown(
    "### 1. Quarterly Actual vs Target"
)

chart1 = go.Figure()

chart1.add_trace(
    go.Scatter(
        x=history_trend["PeriodLabel"],
        y=history_trend["QuarterTarget"],
        mode="lines+markers",
        name="Quarter Target",
        line=dict(
            color="#2E7D32",
            width=3
        )
    )
)

chart1.add_trace(
    go.Scatter(
        x=history_trend["PeriodLabel"],
        y=history_trend["QuarterActual"],
        mode="lines+markers",
        name="Quarter Actual",
        line=dict(
            color="#1F77B4",
            width=3
        )
    )
)

chart1.update_layout(
    xaxis_title="Reporting Period",
    yaxis_title="Indicator Value",
    hovermode="x unified"
)

st.plotly_chart(
    chart1,
    use_container_width=True
)

st.caption(
    "Blue = Actual. Green = Target."
)

# ==================================
# CHART 2
# ==================================

st.markdown(
    "### 2. Annual Forecast Index Trend"
)

annual_chart = go.Figure()

annual_chart.add_trace(
    go.Scatter(
        x=history_trend["PeriodLabel"],
        y=history_trend[
            "AnnualForecastRatio"
        ],
        mode="lines+markers",
        name="Annual Forecast",
        line=dict(
            color="#F28E2B",
            width=3
        )
    )
)

annual_chart.add_hline(
    y=1.0,
    line_dash="dash",
    line_color="green"
)

annual_chart.add_hline(
    y=0.8,
    line_dash="dot",
    line_color="red"
)

annual_chart.update_layout(
    xaxis_title="Reporting Period",
    yaxis_title="Forecast Index",
    hovermode="x unified"
)

annual_chart.update_yaxes(
    tickformat=".0%"
)

st.plotly_chart(
    annual_chart,
    use_container_width=True
)

st.caption(
    "Annual forecast outlook trend."
)

# ==================================
# CHART 3
# ==================================

st.markdown(
    "### 3. Life-of-Project Forecast Index Trend"
)

lop_chart = go.Figure()

lop_chart.add_trace(
    go.Scatter(
        x=history_trend["PeriodLabel"],
        y=history_trend[
            "LoPForecastRatio"
        ],
        mode="lines+markers",
        name="LoP Forecast",
        line=dict(
            color="#7030A0",
            width=3
        )
    )
)

lop_chart.add_hline(
    y=1.0,
    line_dash="dash",
    line_color="green"
)

lop_chart.add_hline(
    y=0.8,
    line_dash="dot",
    line_color="red"
)

lop_chart.update_layout(
    xaxis_title="Reporting Period",
    yaxis_title="Forecast Index",
    hovermode="x unified"
)

lop_chart.update_yaxes(
    tickformat=".0%"
)

st.plotly_chart(
    lop_chart,
    use_container_width=True
)

st.caption(
    "Life-of-project forecast outlook trend."
)


# --------------------------------------------------
# PERFORMANCE GAP VISUAL
# --------------------------------------------------

st.divider()

st.subheader("Progress Against Expected Trajectory")


gap_visual1, gap_visual2 = st.columns(2)


with gap_visual1:

    annual_progress_value = (
        current_record.get(
            "AnnualProgress",
            np.nan
        )
    )

    annual_time_value = (
        current_record.get(
            "AnnualTimeProgress",
            np.nan
        )
    )

    annual_chart = go.Figure()

    annual_chart.add_trace(
        go.Bar(
            x=[
                annual_progress_value,
                annual_time_value
            ],
            y=[
                "Actual annual progress",
                "Expected time progress"
            ],
            orientation="h",
            marker_color=[
                "#4472C4",
                "#A5A5A5"
            ],
            text=[
                safe_percentage(
                    annual_progress_value
                ),
                safe_percentage(
                    annual_time_value
                )
            ],
            textposition="auto"
        )
    )

    annual_chart.update_layout(
        title="Annual Progress",
        xaxis_tickformat=".0%",
        xaxis_title="Share of annual target or time",
        yaxis_title="",
        showlegend=False,
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20
        )
    )

    st.plotly_chart(
        annual_chart,
        use_container_width=True
    )


with gap_visual2:

    lop_progress_value = current_record.get(
        "LoPProgress",
        np.nan
    )

    lop_time_value = current_record.get(
        "LoPTimeProgress",
        np.nan
    )

    lop_chart = go.Figure()

    lop_chart.add_trace(
        go.Bar(
            x=[
                lop_progress_value,
                lop_time_value
            ],
            y=[
                "Actual LoP progress",
                "Expected time progress"
            ],
            orientation="h",
            marker_color=[
                "#4472C4",
                "#A5A5A5"
            ],
            text=[
                safe_percentage(
                    lop_progress_value
                ),
                safe_percentage(
                    lop_time_value
                )
            ],
            textposition="auto"
        )
    )

    lop_chart.update_layout(
        title="Life-of-Project Progress",
        xaxis_tickformat=".0%",
        xaxis_title="Share of LoP target or time",
        yaxis_title="",
        showlegend=False,
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20
        )
    )

    st.plotly_chart(
        lop_chart,
        use_container_width=True
    )


# --------------------------------------------------
# MANAGEMENT INSIGHT
# --------------------------------------------------

st.divider()

st.subheader("Management Insight")


insight_messages = []


if quarter_status == "Not Scheduled":

    insight_messages.append(
        "No target was scheduled for the selected quarter."
    )

elif quarter_status == "Off Track":

    insight_messages.append(
        "Current-quarter achievement is materially below "
        "the scheduled quarterly target."
    )

elif quarter_status == "At Risk":

    insight_messages.append(
        "Current-quarter achievement is below target and "
        "requires close monitoring."
    )

elif quarter_status == "On Track":

    insight_messages.append(
        "Current-quarter achievement is meeting or "
        "exceeding the scheduled target."
    )


insight_messages.append(
    gap_text(
        annual_gap,
        "Annual"
    )
)


insight_messages.append(
    gap_text(
        lop_gap,
        "LoP"
    )
)


if (
    annual_status == "Off Track"
    or lop_status == "Off Track"
):

    action_text = (
        "Suggested review: verify data quality, examine "
        "implementation constraints, review the remaining "
        "targets, and agree feasible corrective actions."
    )

elif (
    annual_status == "At Risk"
    or lop_status == "At Risk"
):

    action_text = (
        "Suggested review: monitor the next reporting "
        "period closely and assess whether additional "
        "implementation support is needed."
    )

else:

    action_text = (
        "Suggested review: maintain the current pace and "
        "continue routine monitoring."
    )


insight_html = "<br>".join(
    "• " + message
    for message in insight_messages
)


st.markdown(
    f"""
    <div class="insight-card">
    <strong>Monitoring interpretation</strong><br>
    {insight_html}<br><br>
    <strong>{action_text}</strong>
    </div>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="method-note">
    <strong>Human review required:</strong><br>
    The indicator status and forecast are decision-support
    signals. MEL and program staff should consider the
    indicator definition, reporting schedule, data quality,
    seasonality, and implementation context before action.
    </div>
    """,
    unsafe_allow_html=True
)


# --------------------------------------------------
# DETAILED HISTORY AND DOWNLOAD
# --------------------------------------------------

st.divider()

st.subheader("Detailed Quarterly History")


display_columns = [
    column
    for column in [
        "PeriodLabel",
        "QuarterTarget",
        "QuarterActual",
        "AchievementRatio",
        "QuarterStatus",
        "AnnualTarget",
        "CurrentYearActual",
        "AnnualProgress",
        "AnnualForecastRatio",
        "AnnualProgressGap",
        "AnnualStatus",
        "CumulativeActual",
        "LoPProgress",
        "LoPForecastRatio",
        "LoPProgressGap",
        "LoPStatus"
    ]
    if column in history.columns
]


st.dataframe(
    history[display_columns],
    hide_index=True,
    use_container_width=True
)


download_filename = (
    str(selected_indicator_id)
    .replace(" ", "_")
    + "_Indicator_History.xlsx"
)


st.download_button(
    label="Download indicator history",
    data=dataframe_to_excel(
        history[display_columns]
    ),
    file_name=download_filename,
    mime=(
        "application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet"
    )
)


st.caption(
    f"Data source sheet: {selected_sheet}."
)

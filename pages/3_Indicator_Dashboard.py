
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils.data_utils import (
load_dashboard_data,
prepare_numeric_columns,
get_indicator_history
)
from utils.status_logic import (
classify_quarter_status,
classify_forecast_status,
status_icon,
status_color
)
st.set_page_config(
page_title="Indicator Dashboard",
page_icon="🎯",
layout="wide"
)
st.title("Indicator Performance Dashboard")
st.caption(
"Detailed quarterly, annual, and life-of-project "
"monitoring for a selected indicator."
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
        "The following required columns are missing: "
        + ", ".join(missing_columns)
    )
    st.stop()
# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------
st.sidebar.header("Indicator Selection")
project_options = sorted(
    data["Project"]
    .dropna()
    .astype(str)
    .unique()
)
selected_project = st.sidebar.selectbox(
    "Project",
    project_options
)
project_data = data[
    data["Project"] == selected_project
].copy()
indicator_options = (
    project_data[
        [
            "IndicatorID",
            "IndicatorName"
        ]
    ]
    .drop_duplicates()
    .sort_values("IndicatorName")
)
indicator_label_map = {
    (
        f"{row['IndicatorID']} | "
        f"{row['IndicatorName']}"
    ): row["IndicatorID"]
    for _, row in indicator_options.iterrows()
}
selected_indicator_label = (
    st.sidebar.selectbox(
        "Indicator",
        list(indicator_label_map.keys())
    )
)
selected_indicator_id = (
    indicator_label_map[
        selected_indicator_label
    ]
)
indicator_all_data = project_data[
    project_data["IndicatorID"]
    == selected_indicator_id
].copy()
available_years = sorted(
    indicator_all_data["Year"]
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
    indicator_all_data.loc[
        indicator_all_data["Year"]
        == selected_year,
        "Quarter"
    ]
    .dropna()
    .astype(int)
    .unique()
)
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
        "No records are available for the selected "
        "indicator and reporting period."
    )
st.stop()
current_record = history.iloc[-1]
# --------------------------------------------------
# RECALCULATE STATUS
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
# HELPER FUNCTIONS
# --------------------------------------------------
def safe_number(
    value,
    decimals=0
):
    if pd.isna(value):
        return "No Data"
    return f"{value:,.{decimals}f}"
def safe_percentage(value):
    if pd.isna(value):
        return "No Data"
    return f"{value * 100:,.1f}%"
def show_progress_bar(
    value,
    label
):
    st.write(label)
    if pd.isna(value):
        st.caption("No data available.")
        return
    display_value = max(
        0.0,
        min(float(value), 1.0)
)
    st.progress(display_value)
    if value > 1.0:
        st.caption(
            f"{value * 100:,.1f}% "
            "of target or projected target"
        )
    else:
        st.caption(
        f"{value * 100:,.1f}%"
    )
def gap_message(
    gap,
    horizon_name
):
    if pd.isna(gap):
        return (
            f"{horizon_name} progress gap "
            "cannot be calculated."
        )
    percentage_gap = abs(
        gap * 100
    )
    if gap > 0.02:
        return (
            f"{horizon_name} performance is "
            f"{percentage_gap:,.1f}% ahead of "
            "the expected time-based trajectory."
        )
    if gap < -0.02:
        return (
            f"{horizon_name} performance is "
            f"{percentage_gap:,.1f}% behind "
            "the expected time-based trajectory."
        )
    return (
        f"{horizon_name} performance is broadly "
        "aligned with the expected trajectory."
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
str(selected_project)
)
profile2.metric(
"Current Period",
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
),
decimals=1
)
)
st.markdown(
f"**Indicator:** "
f"{current_record['IndicatorName']}"
)
baseline = current_record.get(
"Baseline",
np.nan
)
if not pd.isna(baseline):
    st.caption(
        f"Baseline: "
        f"{safe_number(baseline, decimals=2)}"
    )
st.divider()
# --------------------------------------------------
# THREE MONITORING HORIZONS
# --------------------------------------------------
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
safe_number(
quarter_target,
decimals=1
)
)
st.metric(
"Quarter Actual",
safe_number(
quarter_actual,
decimals=1
)
)
st.metric(
"Achievement",
safe_percentage(
quarter_ratio
)
)
if quarter_status == "Not Scheduled":
    st.info(
        "No achievement was scheduled for "
        "this quarter."
    )
else:
    show_progress_bar(
        quarter_ratio,
        "Quarter achievement"
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
annual_gap = current_record.get(
"AnnualProgressGap",
np.nan
)
st.metric(
"Annual Target",
safe_number(
annual_target,
decimals=1
)
)
st.metric(
"Current Year Actual",
safe_number(
current_year_actual,
decimals=1
)
)
st.metric(
"Pace-Based Annual Forecast",
safe_percentage(
annual_ratio
),
delta=(
None
if pd.isna(annual_gap)
else f"{annual_gap * 100:+.1f}% gap"
)
)
show_progress_bar(
annual_ratio,
"Projected annual achievement"
)
st.caption(
gap_message(
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
lop_gap = current_record.get(
"LoPProgressGap",
np.nan
)
st.metric(
"LoP Target",
safe_number(
lop_target,
decimals=1
)
)
st.metric(
"Cumulative Actual",
safe_number(
cumulative_actual,
decimals=1
)
)
st.metric(
"Pace-Based LoP Forecast",
safe_percentage(
lop_ratio
),
delta=(
None
if pd.isna(lop_gap)
else f"{lop_gap * 100:+.1f}% gap"
)
)
show_progress_bar(
lop_ratio,
"Projected LoP achievement"
)
st.caption(
gap_message(
lop_gap,
"LoP"
)
)
st.divider()
# --------------------------------------------------
# ACTUAL, TARGET, AND FORECAST TREND
# --------------------------------------------------
st.subheader(
"Actual, Target, and Forecast Trend"
)
full_indicator_history = (
indicator_all_data
.sort_values("PeriodIndex")
.copy()
)
current_ratio = current_record.get(
"AR_Original",
current_record.get(
"AchievementRatio",
np.nan
)
)
full_indicator_history[
"ForecastActual"
] = np.nan
future_mask = (
full_indicator_history["PeriodIndex"]
> selected_period
)
if not pd.isna(current_ratio):
    valid_future_target = (
        future_mask
        & full_indicator_history[
            "QuarterTarget"
        ].notna()
    )
full_indicator_history.loc[
valid_future_target,
"ForecastActual"
] = (
current_ratio
* full_indicator_history.loc[
valid_future_target,
"QuarterTarget"
]
)
chart = go.Figure()
chart.add_trace(
go.Scatter(
x=history["PeriodLabel"],
y=history["QuarterActual"],
mode="lines+markers",
name="Actual",
line=dict(
color="#1F77B4",
width=3
)
)
)
chart.add_trace(
go.Scatter(
x=full_indicator_history[
"PeriodLabel"
],
y=full_indicator_history[
"QuarterTarget"
],
mode="lines+markers",
name="Target",
line=dict(
color="#2E7D32",
width=2
)
)
)
forecast_data = full_indicator_history[
full_indicator_history[
"ForecastActual"
].notna()
].copy()
if not forecast_data.empty:
    chart.add_trace(
        go.Scatter(
            x=forecast_data["PeriodLabel"],
            y=forecast_data["ForecastActual"],
            mode="lines+markers",
            name="Pace-Based Forecast",
            line=dict(
                color="#F28E2B",
                width=3,
                dash="dash"
            )
        )
    )
chart.update_layout(
xaxis_title="Project Reporting Period",
yaxis_title=(
str(
current_record.get(
"Unit",
"Indicator value"
)
)
),
legend_title="Series",
hovermode="x unified",
margin=dict(
l=20,
r=20,
t=30,
b=20
)
)
st.plotly_chart(
chart,
use_container_width=True
)
st.caption(
"The orange forecast line uses the current "
"original achievement ratio as a pace-based "
"persistence forecast applied to future "
"quarterly targets."
)
# --------------------------------------------------
# MANAGEMENT INSIGHT
# --------------------------------------------------
st.subheader("Management Insight")
insights = []
if quarter_status == "Off Track":
    insights.append(
        "Current-quarter achievement is materially "
        "below the quarterly target."
    )
elif quarter_status == "At Risk":
    insights.append(
        "Current-quarter achievement is below target "
        "and requires monitoring."
    )
elif quarter_status == "On Track":
    insights.append(
        "Current-quarter achievement is meeting or "
        "exceeding the quarterly target."
    )
if not pd.isna(annual_gap):
    insights.append(
        gap_message(
            annual_gap,
            "Annual"
        )
    )
if not pd.isna(lop_gap):
    insights.append(
        gap_message(
            lop_gap,
            "LoP"
        )
    )
if (
    annual_status == "Off Track"
    or lop_status == "Off Track"
):
    suggested_action = (
        "Suggested management review: examine the "
        "implementation plan, remaining targets, "
        "reporting completeness, and feasible "
        "corrective actions."
    )
elif (
    annual_status == "At Risk"
    or lop_status == "At Risk"
):
    suggested_action = (
        "Suggested management review: monitor the "
        "next reporting period closely and assess "
        "whether implementation adjustments are needed."
    )
else:
    suggested_action = (
        "Suggested management review: maintain the "
        "current implementation pace and continue "
        "routine monitoring."
    )
for insight in insights:
    st.write(
        "• " + insight
    )
st.info(suggested_action)
st.warning(
    "These signals support management discussion. "
    "They do not replace indicator-specific technical "
    "interpretation or program staff validation."
)
# --------------------------------------------------
# PERFORMANCE HISTORY
# ---------
with st.expander(
    "View detailed quarterly history"
):
    history_columns = [
        column
        for column in [
            "PeriodLabel",
            "QuarterTarget",
            "QuarterActual",
            "AchievementRatio",
            "AnnualTarget",
            "CurrentYearActual",
            "AnnualForecastRatio",
            "AnnualProgressGap",
            "CumulativeActual",
            "LoPForecastRatio",
            "LoPProgressGap",
            "QuarterStatus",
            "AnnualStatus",
            "LoPStatus"
        ]
        if column in history.columns
    ]
    st.dataframe(
        history[history_columns],
        hide_index=True,
        use_container_width=True
    )

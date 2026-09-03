
import streamlit as st
import pandas as pd
import plotly.express as px
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
st.set_page_config(
    page_title="Portfolio Dashboard",
    page_icon="📊",
    layout="wide"
)
st.title("Portfolio Dashboard")
st.caption(
    "Executive overview of project and indicator performance "
    "for the selected reporting period."
)
try:
    data, selected_sheet, available_sheets = (
    load_dashboard_data()
    )
except Exception as error:
    st.error(
        "The dashboard dataset could not be loaded."
    )
    st.exception(error)
    st.stop()
data = prepare_numeric_columns(data)
required_columns = [
    "IndicatorID",
    "Project",
    "Year",
    "Quarter",
    "PeriodIndex"
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
st.sidebar.header("Reporting Period")
available_years = sorted(
    data["Year"].dropna().astype(int).unique()
)
selected_year = st.sidebar.selectbox(
    "Project Year",
    available_years,
    index=len(available_years) - 1
)
selected_quarter = st.sidebar.selectbox(
    "Quarter",
    [1, 2, 3, 4],
    index=3
)
snapshot = create_period_snapshot(
    data=data,
    year=selected_year,
    quarter=selected_quarter
)
if "AchievementRatio" in snapshot.columns:
    snapshot["QuarterStatus"] = snapshot.apply(
        classify_quarter_status,
        axis=1
    )
if "AnnualForecastRatio" in snapshot.columns:
    snapshot["AnnualStatus"] = (
        snapshot["AnnualForecastRatio"]
        .apply(classify_forecast_status)
    )
if "LoPForecastRatio" in snapshot.columns:
    snapshot["LoPStatus"] = (
        snapshot["LoPForecastRatio"]
        .apply(classify_forecast_status)
    )
st.info(
    f"Reporting snapshot: Year {selected_year}, "
    f"Quarter {selected_quarter}. "
    f"Loaded from sheet: {selected_sheet}"
)
projects_count = snapshot["Project"].nunique()
indicators_count = snapshot["IndicatorID"].nunique()
on_track_count = (
    snapshot["LoPStatus"].eq("On Track").sum()
    if "LoPStatus" in snapshot.columns
    else 0
)
at_risk_count = (
    snapshot["LoPStatus"].eq("At Risk").sum()
    if "LoPStatus" in snapshot.columns
    else 0
)
off_track_count = (
    snapshot["LoPStatus"].eq("Off Track").sum()
    if "LoPStatus" in snapshot.columns
    else 0
)
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric(
    "Projects",
    f"{projects_count:,}"
)
kpi2.metric(
    "Indicators",
    f"{indicators_count:,}"
)
kpi3.metric(
    "🟢 On Track",
    f"{on_track_count:,}"
)
kpi4.metric(
    "🟡 At Risk",
    f"{at_risk_count:,}"
)
kpi5.metric(
    "🔴 Off Track",
    f"{off_track_count:,}"
)
st.divider()
left_column, right_column = st.columns(
    [1.4, 1]
)
with left_column:
    st.subheader("Project Health Summary")
    if "LoPStatus" in snapshot.columns:
        project_health = (
            snapshot
            .groupby(
                ["Project", "LoPStatus"]
            )
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        required_statuses = [
            "On Track",
            "At Risk",
            "Off Track",
            "No Data"
        ]
        for status in required_statuses:
            if status not in project_health.columns:
                project_health[status] = 0
        project_health["Indicators"] = (
            project_health[
                required_statuses
            ].sum(axis=1)
        )
        project_health["RiskScore"] = (
            project_health["Off Track"] * 2
                + project_health["At Risk"]
        )
        def overall_project_status(row):
            if row["Indicators"] == 0:
                return "No Data"
            off_track_share = (
                row["Off Track"]
                / row["Indicators"]
        )
            at_risk_or_off_share = (
                row["Off Track"]
                + row["At Risk"]
            ) / row["Indicators"]
            if off_track_share >= 0.30:
                return "Off Track"
            if at_risk_or_off_share >= 0.30:
                return "At Risk"
            return "On Track"
        project_health["OverallStatus"] = (
            project_health.apply(
                overall_project_status,
                axis=1
            )
        )
        project_health["Overall"] = (
            project_health["OverallStatus"]
            .apply(
                lambda status:
                f"{status_icon(status)} {status}"
            )
        )
        project_health = project_health.sort_values(
            "RiskScore",
            ascending=False
        )
        st.dataframe(
            project_health[
                [
                    "Project",
                    "Indicators",
                    "On Track",
                    "At Risk",
                    "Off Track",
                    "Overall"
                ]
            ],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning(
            "LoPStatus is not available in the dataset."
        )
with right_column:
    st.subheader("Portfolio Risk Distribution")
    if "LoPStatus" in snapshot.columns:
        risk_distribution = (
            snapshot["LoPStatus"]
            .value_counts()
            .rename_axis("Status")
            .reset_index(name="Indicators")
        )
        status_colors = {
            "On Track": "#2E7D32",
            "At Risk": "#F9A825",
            "Off Track": "#C62828",
            "No Data": "#9E9E9E"
        }
        risk_chart = px.pie(
            risk_distribution,
            names="Status",
            values="Indicators",
            hole=0.58,
            color="Status",
            color_discrete_map=status_colors
        )
        risk_chart.update_layout(
            showlegend=True,
            margin=dict(
                l=10,
                r=10,
                t=20,
                b=10
            )
        )
        st.plotly_chart(
            risk_chart,
            use_container_width=True
        )
st.divider()
st.subheader("Indicators Requiring Priority Attention")
if (
    "LoPStatus" in snapshot.columns
    and "LoPForecastRatio" in snapshot.columns
):
    risk_indicators = snapshot[
        snapshot["LoPStatus"].isin(
            ["Off Track", "At Risk"]
            )
    ].copy()
    available_display_columns = [
        column
        for column in [
            "Project",
            "IndicatorID",
            "IndicatorName",
            "Year",
            "Quarter",
            "AnnualForecastRatio",
            "AnnualProgressGap",
            "LoPForecastRatio",
            "LoPProgressGap",
            "AnnualStatus",
            "LoPStatus"
        ]
        if column in risk_indicators.columns
    ]
    risk_indicators = risk_indicators.sort_values(
        by="LoPForecastRatio",
        ascending=True
    )
    st.dataframe(
        risk_indicators[
            available_display_columns
        ].head(20),
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning(
        "Forecast ratio fields are not available."
    )
st.caption(
    "The portfolio dashboard shows the latest observation "
    "available up to the selected reporting period."
)
# ==================================================
# EXECUTIVE PROJECT RANKING
# ==================================================

st.divider()

st.subheader("🏆 Project Performance Ranking")

project_ranking = (
    snapshot
    .groupby("Project")
    .agg(
        AnnualForecast=(
            "AnnualForecastRatio",
            "median"
        ),
        LoPForecast=(
            "LoPForecastRatio",
            "median"
        )
    )
    .reset_index()
)

project_ranking["AnnualForecast"] = (
    project_ranking["AnnualForecast"] * 100
).round(1)

project_ranking["LoPForecast"] = (
    project_ranking["LoPForecast"] * 100
).round(1)

project_ranking = (
    project_ranking
    .sort_values(
        "LoPForecast",
        ascending=False
    )
)

st.dataframe(
    project_ranking,
    hide_index=True,
    use_container_width=True
)
# ==================================================
# PORTFOLIO EARLY WARNING
# ==================================================

st.divider()

st.subheader("🚨 Portfolio Early Warning")

portfolio_warning = (
    snapshot
    .groupby("Project")
    .agg(
        AnnualForecast=(
            "AnnualForecastRatio",
            "median"
        ),
        LoPForecast=(
            "LoPForecastRatio",
            "median"
        )
    )
    .reset_index()
)

portfolio_warning["AnnualForecast"] = (
    portfolio_warning["AnnualForecast"] * 100
).round(1)

portfolio_warning["LoPForecast"] = (
    portfolio_warning["LoPForecast"] * 100
).round(1)

portfolio_warning["GapToTarget"] = (
    portfolio_warning["LoPForecast"] - 100
).round(1)

st.dataframe(
    portfolio_warning.sort_values(
        "GapToTarget"
    ),
    hide_index=True,
    use_container_width=True
)
# ==================================================
# PROJECTS REQUIRING IMMEDIATE ATTENTION
# ==================================================

st.divider()

st.subheader("🔴 Projects Requiring Immediate Attention")

attention_projects = (
    portfolio_warning
    .sort_values(
        "GapToTarget"
    )
    .head(5)
)

st.bar_chart(
    attention_projects.set_index(
        "Project"
    )[
        "GapToTarget"
    ]
)
# ==================================================
# EXECUTIVE PORTFOLIO RISK HEATMAP
# ==================================================

st.divider()

st.subheader("🗺️ Executive Portfolio Risk Heatmap")

portfolio_heatmap = (
    snapshot
    .groupby("Project")
    .agg(
        AnnualForecast=(
            "AnnualForecastRatio",
            "median"
        ),
        LoPForecast=(
            "LoPForecastRatio",
            "median"
        )
    )
    .reset_index()
)

def portfolio_status(value):

    if value >= 1.00:
        return "🟢 On Track"

    elif value >= 0.85:
        return "🟡 At Risk"

    else:
        return "🔴 Off Track"


portfolio_heatmap["Annual Status"] = (
    portfolio_heatmap["AnnualForecast"]
    .apply(portfolio_status)
)

portfolio_heatmap["LoP Status"] = (
    portfolio_heatmap["LoPForecast"]
    .apply(portfolio_status)
)

st.dataframe(
    portfolio_heatmap[
        [
            "Project",
            "Annual Status",
            "LoP Status"
        ]
    ],
    hide_index=True,
    use_container_width=True
)

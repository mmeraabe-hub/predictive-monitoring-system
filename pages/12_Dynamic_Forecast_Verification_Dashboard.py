import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.database_utils import DB_FILE


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="AI Forecast Verification & Prediction",
    page_icon="📈",
    layout="wide"
)

st.title(
    "📈 AI Forecast Verification & Prediction Dashboard"
)

st.caption(
    "Machine-learning forecasts, prediction-verification "
    "records, and strategic Annual and Life-of-Project "
    "outlooks generated from the latest promoted monitoring data."
)


# ==================================================
# LOAD DATA
# ==================================================

@st.cache_data(ttl=60)
def load_data():

    connection = sqlite3.connect(
        str(DB_FILE)
    )

    try:

        verification_metrics = pd.read_sql_query(
            """
            SELECT *
            FROM forecast_verification_metrics
            ORDER BY EvaluationTimestampUTC DESC
            """,
            connection
        )

        project_metrics = pd.read_sql_query(
            """
            SELECT *
            FROM forecast_verification_by_project
            ORDER BY ProjectID
            """,
            connection
        )

        prediction_archive = pd.read_sql_query(
            """
            SELECT *
            FROM prediction_archive
            ORDER BY
                ProjectID,
                IndicatorID,
                PeriodIndex
            """,
            connection
        )

        horizon_forecast = pd.read_sql_query(
            """
            SELECT *
            FROM horizon_forecast
            ORDER BY
                ProjectID,
                IndicatorID,
                ForecastHorizon
            """,
            connection
        )

        horizon_performance = pd.read_sql_query(
            """
            SELECT *
            FROM horizon_model_performance
            ORDER BY
                ForecastHorizon,
                GovernanceRank
            """,
            connection
        )

    finally:

        connection.close()

    return (
        verification_metrics,
        project_metrics,
        prediction_archive,
        horizon_forecast,
        horizon_performance
    )


try:

    (
        metrics_df,
        project_df,
        archive_df,
        horizon_forecast_df,
        horizon_performance_df
    ) = load_data()

except Exception as error:

    st.error(
        "Forecast dashboard data could not be loaded."
    )

    st.exception(
        error
    )

    st.stop()


# ==================================================
# DATA VALIDATION
# ==================================================

if metrics_df.empty:

    st.warning(
        "No promoted forecast-verification metrics are available."
    )

    st.stop()


if archive_df.empty:

    st.warning(
        "No promoted prediction-verification records are available."
    )

    st.stop()


required_archive_columns = [
    "ProjectID",
    "IndicatorID",
    "PeriodIndex",
    "PeriodLabel",
    "ActualValue",
    "PredictedValue",
    "AbsoluteError",
    "ForecastStatus"
]

missing_archive_columns = [
    column
    for column in required_archive_columns
    if column not in archive_df.columns
]

if missing_archive_columns:

    st.error(
        "The prediction archive is missing required columns: "
        + ", ".join(
            missing_archive_columns
        )
    )

    st.stop()


numeric_archive_columns = [
    "Year",
    "Quarter",
    "PeriodIndex",
    "CurrentActualValue",
    "ActualValue",
    "PredictedValue",
    "SignedError",
    "AbsoluteError",
    "SquaredError"
]

for column in numeric_archive_columns:

    if column in archive_df.columns:

        archive_df[column] = pd.to_numeric(
            archive_df[column],
            errors="coerce"
        )


numeric_project_columns = [
    "VerifiedForecasts",
    "MeanAbsoluteError",
    "MedianAbsoluteError",
    "MaximumAbsoluteError",
    "RootMeanSquaredError"
]

for column in numeric_project_columns:

    if column in project_df.columns:

        project_df[column] = pd.to_numeric(
            project_df[column],
            errors="coerce"
        )


numeric_horizon_columns = [
    "CurrentAchievementRatio",
    "ForecastAchievementRatio",
    "ForecastGapToTarget",
    "EvaluationMAE",
    "EvaluationRMSE"
]

for column in numeric_horizon_columns:

    if column in horizon_forecast_df.columns:

        horizon_forecast_df[column] = pd.to_numeric(
            horizon_forecast_df[column],
            errors="coerce"
        )


metrics_row = metrics_df.iloc[0]

global_project_options = sorted(
    archive_df[
        "ProjectID"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

global_indicator_options = sorted(
    archive_df[
        "IndicatorID"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


# ==================================================
# CURRENT EVALUATION INFORMATION
# ==================================================

st.success(
    "Latest forecast evaluation: "
    f"{metrics_row['EvaluationTimestampUTC']} | "
    f"Quarterly champion: {metrics_row['Model']} | "
    f"Prediction-verification records: "
    f"{int(metrics_row['VerifiedForecasts']):,}"
)


# ==================================================
# 1. FORECAST VERIFICATION OVERVIEW
# ==================================================

st.divider()

st.subheader(
    "1. Forecast Verification Overview"
)

overview_col1, overview_col2, overview_col3, overview_col4 = (
    st.columns(4)
)

overview_col1.metric(
    "Verification Records",
    f"{int(metrics_row['VerifiedForecasts']):,}"
)

overview_col2.metric(
    "Mean Absolute Error",
    f"{float(metrics_row['MeanAbsoluteError']):.4f}"
)

overview_col3.metric(
    "Median Absolute Error",
    f"{float(metrics_row['MedianAbsoluteError']):.4f}"
)

overview_col4.metric(
    "Root Mean Squared Error",
    f"{float(metrics_row['RootMeanSquaredError']):.4f}"
)


detail_col1, detail_col2, detail_col3, detail_col4 = (
    st.columns(4)
)

detail_col1.metric(
    "90th Percentile Error",
    f"{float(metrics_row['P90AbsoluteError']):.4f}"
)

detail_col2.metric(
    "95th Percentile Error",
    f"{float(metrics_row['P95AbsoluteError']):.4f}"
)

detail_col3.metric(
    "Maximum Error",
    f"{float(metrics_row['MaximumAbsoluteError']):.4f}"
)

detail_col4.metric(
    "Exact Predictions",
    f"{int(metrics_row['ZeroErrorForecasts']):,}"
)


# ==================================================
# 2. PREDICTION VERIFICATION COVERAGE
# ==================================================

st.divider()

st.subheader(
    "2. Prediction Verification Coverage"
)

status_counts = (
    archive_df[
        "ForecastStatus"
    ]
    .fillna(
        "Unknown"
    )
    .astype(str)
    .value_counts()
    .rename_axis(
        "ForecastStatus"
    )
    .reset_index(
        name="Records"
    )
)

status_chart = px.pie(
    status_counts,
    names="ForecastStatus",
    values="Records",
    hole=0.45,
    color="ForecastStatus",
    color_discrete_map={
        "Verified":
            "#2E7D32",

        "Pending Actual":
            "#F9A825",

        "Unknown":
            "#90A4AE"
    }
)

status_chart.update_traces(
    textposition="inside",
    textinfo="label+value+percent"
)

status_chart.update_layout(
    margin=dict(
        l=10,
        r=10,
        t=20,
        b=10
    ),
    legend_title_text=""
)

st.plotly_chart(
    status_chart,
    width="stretch",
    key="section2_verification_coverage"
)


coverage_col1, coverage_col2, coverage_col3 = st.columns(3)

coverage_col1.metric(
    "Projects Evaluated",
    archive_df[
        "ProjectID"
    ].nunique()
)

coverage_col2.metric(
    "Indicators Evaluated",
    archive_df[
        "IndicatorID"
    ].nunique()
)

coverage_col3.metric(
    "Verification Records",
    f"{len(archive_df):,}"
)

st.info(
    """
A prediction-verification record represents one
actual-versus-predicted comparison for one indicator and one
reporting period.

One indicator can contribute several verification records
because the indicator is evaluated across several reporting
periods.

These records are used to calculate MAE, RMSE, signed error,
and absolute error for the promoted quarterly forecasting model.
"""
)


# ==================================================
# 3. ANNUAL AND LOP TARGET VS ACTUAL VS ML FORECAST
# ==================================================

st.divider()

st.subheader(
    "3. Annual and Life-of-Project Forecast Comparison"
)

st.caption(
    "Compare targets, current reported results, and "
    "machine-learning forecast values in the indicator's "
    "original unit of measurement."
)

if horizon_forecast_df.empty:

    st.info(
        "No Annual or Life-of-Project ML forecasts "
        "are currently available."
    )

else:

    comparison_projects = sorted(
        horizon_forecast_df[
            "ProjectID"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    comparison_filter1, comparison_filter2 = st.columns(2)

    selected_comparison_project = (
        comparison_filter1.selectbox(
            "Project",
            options=comparison_projects,
            index=0,
            key="section3_annual_lop_project"
        )
    )

    project_horizon_forecasts = (
        horizon_forecast_df[
            horizon_forecast_df[
                "ProjectID"
            ]
            .astype(str)
            .eq(
                selected_comparison_project
            )
        ]
        .copy()
    )

    comparison_indicators = sorted(
        project_horizon_forecasts[
            "IndicatorID"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not comparison_indicators:

        st.info(
            "No indicators are available for the selected project."
        )

    else:

        selected_comparison_indicator = (
            comparison_filter2.selectbox(
                "Indicator",
                options=comparison_indicators,
                index=0,
                key="section3_annual_lop_indicator"
            )
        )

        selected_horizon_forecasts = (
            project_horizon_forecasts[
                project_horizon_forecasts[
                    "IndicatorID"
                ]
                .astype(str)
                .eq(
                    selected_comparison_indicator
                )
            ]
            .copy()
        )

        monitoring_connection = sqlite3.connect(
            str(DB_FILE)
        )

        try:

            indicator_monitoring_history = pd.read_sql_query(
                """
                SELECT
                    Project,
                    IndicatorID,
                    IndicatorName,
                    Unit,
                    Year,
                    Quarter,
                    PeriodIndex,
                    PeriodLabel,
                    AnnualTarget,
                    CurrentYearActual,
                    LoPTarget,
                    CumulativeActual
                FROM dashboard_data
                WHERE Project = ?
                  AND IndicatorID = ?
                ORDER BY PeriodIndex
                """,
                monitoring_connection,
                params=(
                    selected_comparison_project,
                    selected_comparison_indicator
                )
            )

        finally:

            monitoring_connection.close()

        if indicator_monitoring_history.empty:

            st.warning(
                "No monitoring record is available for the "
                "selected project and indicator."
            )

        else:

            numeric_monitoring_columns = [
                "AnnualTarget",
                "CurrentYearActual",
                "LoPTarget",
                "CumulativeActual"
            ]

            for column in numeric_monitoring_columns:

                indicator_monitoring_history[column] = (
                    pd.to_numeric(
                        indicator_monitoring_history[column],
                        errors="coerce"
                    )
                )

            latest_monitoring_record = (
                indicator_monitoring_history
                .sort_values(
                    "PeriodIndex"
                )
                .iloc[-1]
            )

            annual_rows = selected_horizon_forecasts[
                selected_horizon_forecasts[
                    "ForecastHorizon"
                ]
                .astype(str)
                .eq(
                    "Annual"
                )
            ]

            lop_rows = selected_horizon_forecasts[
                selected_horizon_forecasts[
                    "ForecastHorizon"
                ]
                .astype(str)
                .eq(
                    "LoP"
                )
            ]

            annual_target = latest_monitoring_record[
                "AnnualTarget"
            ]

            annual_actual = latest_monitoring_record[
                "CurrentYearActual"
            ]

            lop_target = latest_monitoring_record[
                "LoPTarget"
            ]

            lop_actual = latest_monitoring_record[
                "CumulativeActual"
            ]

            annual_forecast_ratio = (
                float(
                    annual_rows.iloc[0][
                        "ForecastAchievementRatio"
                    ]
                )
                if not annual_rows.empty
                else None
            )

            lop_forecast_ratio = (
                float(
                    lop_rows.iloc[0][
                        "ForecastAchievementRatio"
                    ]
                )
                if not lop_rows.empty
                else None
            )

            annual_forecast_value = (
                annual_forecast_ratio
                *
                float(
                    annual_target
                )
                if (
                    annual_forecast_ratio is not None
                    and
                    pd.notna(
                        annual_target
                    )
                )
                else None
            )

            lop_forecast_value = (
                lop_forecast_ratio
                *
                float(
                    lop_target
                )
                if (
                    lop_forecast_ratio is not None
                    and
                    pd.notna(
                        lop_target
                    )
                )
                else None
            )

            annual_model = (
                str(
                    annual_rows.iloc[0][
                        "ForecastModel"
                    ]
                )
                if not annual_rows.empty
                else "Not available"
            )

            lop_model = (
                str(
                    lop_rows.iloc[0][
                        "ForecastModel"
                    ]
                )
                if not lop_rows.empty
                else "Not available"
            )

            indicator_name = (
                str(
                    latest_monitoring_record[
                        "IndicatorName"
                    ]
                )
                if pd.notna(
                    latest_monitoring_record[
                        "IndicatorName"
                    ]
                )
                else selected_comparison_indicator
            )

            indicator_unit = (
                str(
                    latest_monitoring_record[
                        "Unit"
                    ]
                )
                if pd.notna(
                    latest_monitoring_record[
                        "Unit"
                    ]
                )
                else "Indicator Value"
            )

            st.markdown(
                f"### {indicator_name}"
            )

            st.caption(
                f"Indicator ID: {selected_comparison_indicator} | "
                f"Current period: "
                f"{latest_monitoring_record['PeriodLabel']} | "
                f"Unit: {indicator_unit}"
            )

            annual_chart_column, lop_chart_column = st.columns(2)

            with annual_chart_column:

                st.markdown(
                    "### Annual Outlook"
                )

                annual_chart_data = pd.DataFrame(
                    {
                        "Measure": [
                            "Annual Target",
                            "Current Annual Actual",
                            "Annual ML Forecast"
                        ],
                        "Value": [
                            annual_target,
                            annual_actual,
                            annual_forecast_value
                        ]
                    }
                )

                annual_chart_data[
                    "Value"
                ] = pd.to_numeric(
                    annual_chart_data[
                        "Value"
                    ],
                    errors="coerce"
                )

                annual_chart_data = annual_chart_data.dropna(
                    subset=[
                        "Value"
                    ]
                )

                if annual_chart_data.empty:

                    st.info(
                        "Annual comparison data are not available "
                        "for this indicator."
                    )

                else:

                    annual_chart = px.bar(
                        annual_chart_data,
                        x="Measure",
                        y="Value",
                        color="Measure",
                        text_auto=".4s",
                        color_discrete_map={
                            "Annual Target":
                                "#C62828",

                            "Current Annual Actual":
                                "#2E7D32",

                            "Annual ML Forecast":
                                "#1565C0"
                        },
                        labels={
                            "Measure":
                                "",

                            "Value":
                                indicator_unit
                        }
                    )

                    annual_chart.update_layout(
                        showlegend=False,
                        margin=dict(
                            l=10,
                            r=10,
                            t=20,
                            b=10
                        )
                    )

                    st.plotly_chart(
                        annual_chart,
                        width="stretch",
                        key="section3_annual_ml_chart"
                    )

            with lop_chart_column:

                st.markdown(
                    "### Life-of-Project Outlook"
                )

                lop_chart_data = pd.DataFrame(
                    {
                        "Measure": [
                            "LoP Target",
                            "Current Cumulative Actual",
                            "LoP ML Forecast"
                        ],
                        "Value": [
                            lop_target,
                            lop_actual,
                            lop_forecast_value
                        ]
                    }
                )

                lop_chart_data[
                    "Value"
                ] = pd.to_numeric(
                    lop_chart_data[
                        "Value"
                    ],
                    errors="coerce"
                )

                lop_chart_data = lop_chart_data.dropna(
                    subset=[
                        "Value"
                    ]
                )

                if lop_chart_data.empty:

                    st.info(
                        "Life-of-Project comparison data are "
                        "not available for this indicator."
                    )

                else:

                    lop_chart = px.bar(
                        lop_chart_data,
                        x="Measure",
                        y="Value",
                        color="Measure",
                        text_auto=".4s",
                        color_discrete_map={
                            "LoP Target":
                                "#C62828",

                            "Current Cumulative Actual":
                                "#2E7D32",

                            "LoP ML Forecast":
                                "#7B1FA2"
                        },
                        labels={
                            "Measure":
                                "",

                            "Value":
                                indicator_unit
                        }
                    )

                    lop_chart.update_layout(
                        showlegend=False,
                        margin=dict(
                            l=10,
                            r=10,
                            t=20,
                            b=10
                        )
                    )

                    st.plotly_chart(
                        lop_chart,
                        width="stretch",
                        key="section3_lop_ml_chart"
                    )

            st.info(
                """
**Annual Target** is the planned target for the current
project year.

**Current Annual Actual** is the reported result achieved
so far during the current year.

**Annual ML Forecast** converts the Annual ML forecast ratio
into the indicator's original measurement unit.

**LoP Target** is the final target for the complete project.

**Current Cumulative Actual** is the result achieved to date
across the project lifecycle.

**LoP ML Forecast** converts the Life-of-Project ML forecast
ratio into the indicator's original measurement unit.
"""
            )


# ==================================================
# 4. ABSOLUTE FORECAST ERROR DISTRIBUTION
# ==================================================

st.divider()

st.subheader(
    "4. Absolute Forecast Error Distribution"
)

valid_errors = archive_df.dropna(
    subset=[
        "AbsoluteError"
    ]
).copy()

if valid_errors.empty:

    st.warning(
        "No valid forecast-error records are available."
    )

else:

    distribution_limit = valid_errors[
        "AbsoluteError"
    ].quantile(
        0.99
    )

    distribution_df = valid_errors[
        valid_errors[
            "AbsoluteError"
        ].le(
            distribution_limit
        )
    ].copy()

    error_histogram = px.histogram(
        distribution_df,
        x="AbsoluteError",
        nbins=50,
        labels={
            "AbsoluteError":
                "Absolute Forecast Error"
        }
    )

    error_histogram.add_vline(
        x=float(
            valid_errors[
                "AbsoluteError"
            ].median()
        ),
        line_dash="dash",
        line_color="#2E7D32",
        annotation_text="Median"
    )

    error_histogram.add_vline(
        x=float(
            metrics_row[
                "P95AbsoluteError"
            ]
        ),
        line_dash="dot",
        line_color="#C62828",
        annotation_text="P95"
    )

    error_histogram.update_layout(
        yaxis_title="Verification Records",
        margin=dict(
            l=10,
            r=10,
            t=20,
            b=10
        )
    )

    st.plotly_chart(
        error_histogram,
        width="stretch",
        key="section4_error_distribution"
    )

    st.caption(
        "The histogram is limited to the 99th percentile "
        "for readability. Extreme errors remain included in "
        "the summary metrics and verification explorer."
    )

    maximum_error = float(
        valid_errors[
            "AbsoluteError"
        ].max()
    )

    p95_error = float(
        metrics_row[
            "P95AbsoluteError"
        ]
    )

    if maximum_error > p95_error:

        st.warning(
            "Extreme forecast errors are present. "
            f"The maximum absolute error is {maximum_error:.4f}, "
            f"compared with a 95th-percentile error of "
            f"{p95_error:.4f}. Review the relevant project "
            "and indicator records before interpreting the "
            "result as general model failure."
        )


# ==================================================
# 5. PROJECT FORECAST VERIFICATION SCORECARD
# ==================================================

st.divider()

st.subheader(
    "5. Project Forecast Verification Scorecard"
)

if project_df.empty:

    st.info(
        "No project-level forecast-verification results "
        "are available."
    )

else:

    project_display_columns = [
        "ProjectID",
        "VerifiedForecasts",
        "MeanAbsoluteError",
        "MedianAbsoluteError",
        "RootMeanSquaredError",
        "MaximumAbsoluteError"
    ]

    available_project_columns = [
        column
        for column in project_display_columns
        if column in project_df.columns
    ]

    project_display = project_df[
        available_project_columns
    ].copy()

    if "RootMeanSquaredError" in project_display.columns:

        project_display = project_display.sort_values(
            "RootMeanSquaredError",
            ascending=True
        )

    st.dataframe(
        project_display,
        hide_index=True,
        width="stretch",
        column_config={
            "ProjectID":
                "Project",

            "VerifiedForecasts":
                "Verification Records",

            "MeanAbsoluteError":
                st.column_config.NumberColumn(
                    "MAE",
                    format="%.4f"
                ),

            "MedianAbsoluteError":
                st.column_config.NumberColumn(
                    "Median Error",
                    format="%.4f"
                ),

            "RootMeanSquaredError":
                st.column_config.NumberColumn(
                    "RMSE",
                    format="%.4f"
                ),

            "MaximumAbsoluteError":
                st.column_config.NumberColumn(
                    "Maximum Error",
                    format="%.4f"
                )
        }
    )


# ==================================================
# 6. FORECAST VERIFICATION EXPLORER
# ==================================================

st.divider()

st.subheader(
    "6. Forecast Verification Explorer"
)

explorer_filter1, explorer_filter2, explorer_filter3 = (
    st.columns(3)
)

selected_explorer_projects = explorer_filter1.multiselect(
    "Projects",
    options=global_project_options,
    default=global_project_options,
    key="section6_explorer_projects"
)

selected_explorer_indicators = explorer_filter2.multiselect(
    "Indicators",
    options=global_indicator_options,
    key="section6_explorer_indicators"
)

status_options = sorted(
    archive_df[
        "ForecastStatus"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_explorer_statuses = explorer_filter3.multiselect(
    "Forecast Status",
    options=status_options,
    default=status_options,
    key="section6_explorer_status"
)

explorer_df = archive_df.copy()

if selected_explorer_projects:

    explorer_df = explorer_df[
        explorer_df[
            "ProjectID"
        ]
        .astype(str)
        .isin(
            selected_explorer_projects
        )
    ]

if selected_explorer_indicators:

    explorer_df = explorer_df[
        explorer_df[
            "IndicatorID"
        ]
        .astype(str)
        .isin(
            selected_explorer_indicators
        )
    ]

if selected_explorer_statuses:

    explorer_df = explorer_df[
        explorer_df[
            "ForecastStatus"
        ]
        .astype(str)
        .isin(
            selected_explorer_statuses
        )
    ]

explorer_columns = [
    "ProjectID",
    "IndicatorID",
    "IndicatorName",
    "Year",
    "Quarter",
    "PeriodLabel",
    "CurrentActualValue",
    "ActualValue",
    "PredictedValue",
    "SignedError",
    "AbsoluteError",
    "ForecastStatus"
]

available_explorer_columns = [
    column
    for column in explorer_columns
    if column in explorer_df.columns
]

st.dataframe(
    explorer_df[
        available_explorer_columns
    ],
    hide_index=True,
    width="stretch"
)

st.caption(
    f"Verification records displayed: {len(explorer_df):,}"
)


# ==================================================
# 7. STRATEGIC AI FORECASTING OUTLOOK
# ==================================================

st.divider()

st.subheader(
    "7. Strategic AI Forecasting Outlook"
)

st.caption(
    "Machine-learning models estimate expected year-end "
    "and project-completion performance. The existing "
    "next-quarter forecasting and verification workflow "
    "remains unchanged."
)

if horizon_forecast_df.empty:

    st.info(
        "No Annual or Life-of-Project machine-learning "
        "forecasts are currently available."
    )

else:

    strategic_projects = sorted(
        horizon_forecast_df[
            "ProjectID"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    strategic_filter1, strategic_filter2 = st.columns(2)

    selected_strategic_project = (
        strategic_filter1.selectbox(
            "Forecast Project",
            options=strategic_projects,
            index=0,
            key="section7_strategic_project"
        )
    )

    project_strategic_data = horizon_forecast_df[
        horizon_forecast_df[
            "ProjectID"
        ]
        .astype(str)
        .eq(
            selected_strategic_project
        )
    ].copy()

    strategic_indicators = sorted(
        project_strategic_data[
            "IndicatorID"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not strategic_indicators:

        st.info(
            "No strategic forecasts are available for the "
            "selected project."
        )

    else:

        selected_strategic_indicator = (
            strategic_filter2.selectbox(
                "Forecast Indicator",
                options=strategic_indicators,
                index=0,
                key="section7_strategic_indicator"
            )
        )

        selected_strategic_data = project_strategic_data[
            project_strategic_data[
                "IndicatorID"
            ]
            .astype(str)
            .eq(
                selected_strategic_indicator
            )
        ].copy()

        annual_strategic_rows = selected_strategic_data[
            selected_strategic_data[
                "ForecastHorizon"
            ]
            .astype(str)
            .eq(
                "Annual"
            )
        ]

        lop_strategic_rows = selected_strategic_data[
            selected_strategic_data[
                "ForecastHorizon"
            ]
            .astype(str)
            .eq(
                "LoP"
            )
        ]

        current_ratio_values = selected_strategic_data[
            "CurrentAchievementRatio"
        ].dropna()

        current_ratio = (
            float(
                current_ratio_values.iloc[0]
            )
            if not current_ratio_values.empty
            else None
        )

        annual_forecast = (
            float(
                annual_strategic_rows.iloc[0][
                    "ForecastAchievementRatio"
                ]
            )
            if not annual_strategic_rows.empty
            else None
        )

        lop_forecast = (
            float(
                lop_strategic_rows.iloc[0][
                    "ForecastAchievementRatio"
                ]
            )
            if not lop_strategic_rows.empty
            else None
        )

        annual_model = (
            str(
                annual_strategic_rows.iloc[0][
                    "ForecastModel"
                ]
            )
            if not annual_strategic_rows.empty
            else "Not available"
        )

        lop_model = (
            str(
                lop_strategic_rows.iloc[0][
                    "ForecastModel"
                ]
            )
            if not lop_strategic_rows.empty
            else "Not available"
        )

        st.info(
            """
**Current Performance** is the latest observed Achievement
Ratio for the selected indicator.

**Expected Year-End Performance** is the machine-learning
estimate of where the indicator is likely to finish at the
end of the current project year.

**Expected Project Completion Performance** is the
machine-learning estimate of where the indicator is likely
to finish when the project reaches completion.

A value of 100% represents full target achievement.
"""
        )

        strategic_card1, strategic_card2, strategic_card3 = (
            st.columns(3)
        )

        strategic_card1.metric(
            "Current Performance",
            (
                f"{current_ratio:.2%}"
                if current_ratio is not None
                else "Not available"
            )
        )

        strategic_card2.metric(
            "Expected Year-End Performance",
            (
                f"{annual_forecast:.2%}"
                if annual_forecast is not None
                else "Not available"
            )
        )

        if (
            lop_forecast is not None
            and
            pd.notna(lop_forecast)
            and
            0 <= float(lop_forecast) <= 3
        ):

            strategic_card3.metric(
                "Expected Project Completion Performance",
                f"{lop_forecast:.2%}"
            )

        else:

            strategic_card3.warning(
                "LoP ML Forecast Under Validation"
            )

        champion_col1, champion_col2 = st.columns(2)

        champion_col1.success(
            f"""
Annual Forecast Champion

{annual_model}
"""
        )

        champion_col2.success(
            f"""
Life-of-Project Forecast Champion

{lop_model}
"""
        )

        st.info(
            """
Current Performance:
Latest observed achievement ratio for the selected indicator.

Expected Year-End Performance:
Machine-learning estimate of where the indicator is likely
to finish by the end of the current project year.

Expected Project Completion Performance:
Machine-learning estimate of where the indicator is likely
to finish when the project reaches completion.

Annual Forecast Champion:
Best-performing model for annual forecasting based on
lowest RMSE followed by lowest MAE.

Life-of-Project Forecast Champion:
Best-performing model for Life-of-Project forecasting based
on lowest RMSE followed by lowest MAE.

A value of 100% represents full target achievement.
Values above 100% indicate expected over-achievement.
Values below 100% indicate expected under-achievement.
"""
        )
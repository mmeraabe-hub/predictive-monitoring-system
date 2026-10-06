import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.database_utils import DB_FILE


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Dynamic Forecast Verification Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title(
    "📈 Dynamic Forecast Verification Dashboard"
)

st.caption(
    "Current prediction-level forecast verification generated "
    "from the latest approved data, retraining cycle, and "
    "lifecycle promotion."
)


# ==================================================
# LOAD DATA
# ==================================================

@st.cache_data(ttl=60)
def load_data():

    conn = sqlite3.connect(
        str(DB_FILE)
    )

    try:

        verification_metrics = pd.read_sql_query(
            """
            SELECT *
            FROM forecast_verification_metrics
            ORDER BY EvaluationTimestampUTC DESC
            """,
            conn
        )

        project_metrics = pd.read_sql_query(
            """
            SELECT *
            FROM forecast_verification_by_project
            ORDER BY ProjectID
            """,
            conn
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
            conn
        )

    finally:

        conn.close()

    return (
        verification_metrics,
        project_metrics,
        prediction_archive
    )


try:

    (
        metrics_df,
        project_df,
        archive_df
    ) = load_data()

except Exception as error:

    st.error(
        "Forecast verification data could not be loaded."
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
        "No promoted prediction-level forecast records are available."
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


metrics_row = metrics_df.iloc[0]


# ==================================================
# CURRENT EVALUATION INFORMATION
# ==================================================

st.success(
    "Latest forecast evaluation: "
    f"{metrics_row['EvaluationTimestampUTC']} | "
    f"Model: {metrics_row['Model']} | "
    f"Verified forecasts: "
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
    "Verified Forecasts",
    f"{int(metrics_row['VerifiedForecasts']):,}"
)

overview_col2.metric(
    "MAE",
    f"{float(metrics_row['MeanAbsoluteError']):.4f}"
)

overview_col3.metric(
    "Median Error",
    f"{float(metrics_row['MedianAbsoluteError']):.4f}"
)

overview_col4.metric(
    "RMSE",
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
    "Exact Forecasts",
    f"{int(metrics_row['ZeroErrorForecasts']):,}"
)

# ==================================================
# 2. PREDICTION VERIFICATION RECORDS
# ==================================================

st.divider()

st.subheader(
    "2. Prediction Verification Records"
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
    key="forecast_status_pie"
)

project_count = (
    archive_df[
        "ProjectID"
    ]
    .nunique()
)

indicator_count = (
    archive_df[
        "IndicatorID"
    ]
    .nunique()
)

summary_col1, summary_col2, summary_col3 = (
    st.columns(3)
)

summary_col1.metric(
    "Projects Evaluated",
    project_count
)

summary_col2.metric(
    "Indicators Evaluated",
    indicator_count
)

summary_col3.metric(
    "Prediction Records",
    len(
        archive_df
    )
)

st.info(
    """
A prediction verification record represents one
Actual-versus-Predicted comparison.

Example:

Indicator: ARST_003

Period: Y5Q1

Actual Value: 1.0626

Predicted Value: 0.6672

Absolute Error: 0.3954

The current total does not represent the number of
projects or indicators.

It represents the total number of prediction
comparisons generated from the holdout test dataset
during the latest retraining cycle.
"""
)
# ==================================================
# 3. ACTUAL VS PREDICTED VERIFICATION
# ==================================================

st.divider()

st.subheader(
    "3. Actual vs Predicted Verification"
)

project_options = sorted(
    archive_df[
        "ProjectID"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

if not project_options:

    st.info(
        "No projects are available for forecast verification."
    )

else:

    filter_col1, filter_col2 = st.columns(2)

    selected_project = filter_col1.selectbox(
        "Project",
        options=project_options,
        index=0
    )

    project_archive = archive_df[
        archive_df[
            "ProjectID"
        ]
        .astype(str)
        .eq(
            selected_project
        )
    ].copy()

    indicator_options = sorted(
        project_archive[
            "IndicatorID"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not indicator_options:

        st.info(
            "No indicators are available for the selected project."
        )

    else:

        selected_indicator = filter_col2.selectbox(
            "Indicator",
            options=indicator_options,
            index=0
        )

        selected_forecast = project_archive[
            project_archive[
                "IndicatorID"
            ]
            .astype(str)
            .eq(
                selected_indicator
            )
        ].copy()

        selected_forecast = selected_forecast.sort_values(
            "PeriodIndex"
        )

        chart_columns = [
            "PeriodLabel",
            "ActualValue",
            "PredictedValue"
        ]

        if "CurrentActualValue" in selected_forecast.columns:

            chart_columns.append(
                "CurrentActualValue"
            )

        chart_data = selected_forecast[
            chart_columns
        ].melt(
            id_vars=[
                "PeriodLabel"
            ],
            value_vars=[
                column
                for column in [
                    "CurrentActualValue",
                    "ActualValue",
                    "PredictedValue"
                ]
                if column in chart_columns
            ],
            var_name="Series",
            value_name="AchievementRatio"
        )

        series_labels = {
            "CurrentActualValue":
                "Current Actual",

            "ActualValue":
                "Next-Period Actual",

            "PredictedValue":
                "Next-Period Prediction"
        }

        chart_data[
            "Series"
        ] = chart_data[
            "Series"
        ].replace(
            series_labels
        )

        actual_prediction_chart = px.line(
            chart_data,
            x="PeriodLabel",
            y="AchievementRatio",
            color="Series",
            markers=True,
            color_discrete_map={
                "Current Actual":
                    "#607D8B",

                "Next-Period Actual":
                    "#2E7D32",

                "Next-Period Prediction":
                    "#1565C0"
            },
            labels={
                "PeriodLabel":
                    "Reporting Period",

                "AchievementRatio":
                    "Achievement Ratio",

                "Series":
                    ""
            }
        )

        actual_prediction_chart.update_layout(
            margin=dict(
                l=10,
                r=10,
                t=20,
                b=10
            ),
            legend_title_text=""
        )

        st.plotly_chart(
            actual_prediction_chart,
            width="stretch",
            key="dynamic_actual_vs_predicted"
        )

        selected_detail_columns = [
            "PeriodLabel",
            "CurrentActualValue",
            "ActualValue",
            "PredictedValue",
            "SignedError",
            "AbsoluteError"
        ]

        available_detail_columns = [
            column
            for column in selected_detail_columns
            if column in selected_forecast.columns
        ]

        st.dataframe(
            selected_forecast[
                available_detail_columns
            ],
            hide_index=True,
            width="stretch"
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
        yaxis_title="Forecast Records",
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
        key="dynamic_error_distribution"
    )

    st.caption(
        "The histogram is limited to the 99th percentile "
        "for readability. Extreme errors remain included in "
        "the summary metrics and forecast explorer."
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
            "Extreme forecast error detected. "
            f"The maximum absolute error is {maximum_error:.4f}, "
            f"compared with a 95th-percentile error of "
            f"{p95_error:.4f}. Review the associated project "
            "and indicator before interpreting the observation "
            "as model failure."
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
        width="stretch"
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

selected_projects = explorer_filter1.multiselect(
    "Projects",
    options=project_options,
    default=project_options
)

all_indicator_options = sorted(
    archive_df[
        "IndicatorID"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_indicators = explorer_filter2.multiselect(
    "Indicators",
    options=all_indicator_options
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

selected_statuses = explorer_filter3.multiselect(
    "Forecast Status",
    options=status_options,
    default=status_options
)

explorer_df = archive_df.copy()

if selected_projects:

    explorer_df = explorer_df[
        explorer_df[
            "ProjectID"
        ]
        .astype(str)
        .isin(
            selected_projects
        )
    ]

if selected_indicators:

    explorer_df = explorer_df[
        explorer_df[
            "IndicatorID"
        ]
        .astype(str)
        .isin(
            selected_indicators
        )
    ]

if selected_statuses:

    explorer_df = explorer_df[
        explorer_df[
            "ForecastStatus"
        ]
        .astype(str)
        .isin(
            selected_statuses
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
    f"Forecast records displayed: {len(explorer_df):,}"
)


# ==================================================
# METHODOLOGY NOTE
# ==================================================

st.divider()

st.info(
    "This dashboard uses promoted prediction-level results "
    "from the latest approved data and lifecycle retraining "
    "workflow. Actual-versus-predicted verification, error "
    "statistics, project scorecards, and explorer records are "
    "refreshed when forecast-verification staging tables are "
    "promoted through the Model Lifecycle Dashboard."
)
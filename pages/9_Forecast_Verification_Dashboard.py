import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.database_utils import DB_FILE


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Forecast Verification Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title(
    "Forecast Verification Dashboard"
)

st.caption(
    "Evaluate forecast accuracy, verification status, and project forecasting performance."
)


# ==================================================
# LOAD DATA
# ==================================================

@st.cache_data
def load_data():

    conn = sqlite3.connect(DB_FILE)

    try:

        archive = pd.read_sql_query(
            """
            SELECT *
            FROM prediction_archive
            """,
            conn
        )

        metrics = pd.read_sql_query(
            """
            SELECT *
            FROM forecast_verification_metrics
            """,
            conn
        )

        projects = pd.read_sql_query(
            """
            SELECT *
            FROM forecast_verification_by_project
            """,
            conn
        )

    finally:

        conn.close()

    return archive, metrics, projects


try:

    archive_df, metrics_df, project_df = load_data()

except Exception as error:

    st.error(
        "Forecast verification tables could not be loaded."
    )

    st.exception(error)

    st.stop()
    # ==================================================
# KPI SECTION
# ==================================================

if not metrics_df.empty:

    metrics_row = metrics_df.iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Verified Forecasts",
        int(
            metrics_row[
                "VerifiedForecasts"
            ]
        )
    )

    col2.metric(
        "MAE",
        round(
            metrics_row[
                "MeanAbsoluteError"
            ],
            4
        )
    )

    col3.metric(
        "Median Error",
        round(
            metrics_row[
                "MedianAbsoluteError"
            ],
            4
        )
    )

    col4.metric(
        "RMSE",
        round(
            metrics_row[
                "RootMeanSquaredError"
            ],
            4
        )
    )
import sqlite3
import pandas as pd

conn = sqlite3.connect(
    DB_FILE
)
conn = sqlite3.connect(
    DB_FILE
)

tables = pd.read_sql_query(
    """
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name
    """,
    conn
)

conn.close()

st.dataframe(tables)

# ==================================================
# DATA PREPARATION
# ==================================================

numeric_archive_columns = [
    "PredictedValue",
    "ActualValue",
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


verified_df = (
    archive_df[
        archive_df["ForecastStatus"]
        .eq("Verified")
    ]
    .dropna(
        subset=[
            "PredictedValue",
            "ActualValue",
            "AbsoluteError"
        ]
    )
    .copy()
)


pending_df = archive_df[
    archive_df["ForecastStatus"]
    .eq("Pending Actual")
].copy()


# ==================================================
# ADDITIONAL KPI CARDS
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Overview"
)


pending_count = len(pending_df)


p90_error = (
    float(
        metrics_row["P90AbsoluteError"]
    )
    if not metrics_df.empty
    else float("nan")
)


p95_error = (
    float(
        metrics_row["P95AbsoluteError"]
    )
    if not metrics_df.empty
    else float("nan")
)


zero_error_forecasts = (
    int(
        metrics_row["ZeroErrorForecasts"]
    )
    if not metrics_df.empty
    else 0
)


overview1, overview2, overview3, overview4 = (
    st.columns(4)
)


overview1.metric(
    "Pending Actuals",
    f"{pending_count:,}"
)


overview2.metric(
    "90th Percentile Error",
    f"{p90_error:.4f}"
)


overview3.metric(
    "95th Percentile Error",
    f"{p95_error:.4f}"
)


overview4.metric(
    "Exact Forecasts",
    f"{zero_error_forecasts:,}"
)


st.info(
    """
    This dashboard presents a historical Naive Persistence
    backtest on the Original Achievement Ratio scale.

    The 3,915 verified forecasts represent historical
    current-quarter to next-quarter comparisons. They are
    different from the 756 held-out test observations used
    for formal model comparison in the Model Performance
    Dashboard.
    """
)


# ==================================================
# FORECAST STATUS BREAKDOWN
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Status"
)


status_counts = (
    archive_df[
        "ForecastStatus"
    ]
    .fillna("Unknown")
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
        "Verified": "#2E7D32",
        "Pending Actual": "#F9A825",
        "Baseline": "#607D8B",
        "Unknown": "#9E9E9E"
    }
)


status_chart.update_traces(
    textposition="inside",
    textinfo="label+percent+value"
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
    use_container_width=True,
    key="forecast_status_breakdown"
)


# ==================================================
# ERROR DISTRIBUTION
# ==================================================

st.divider()

st.subheader(
    "Absolute Forecast Error Distribution"
)


if verified_df.empty:

    st.warning(
        "No verified forecasts are available."
    )

else:

    distribution_limit = (
        verified_df[
            "AbsoluteError"
        ]
        .quantile(0.99)
    )


    distribution_df = verified_df[
        verified_df["AbsoluteError"]
        .le(distribution_limit)
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
            verified_df[
                "AbsoluteError"
            ].median()
        ),
        line_dash="dash",
        line_color="#2E7D32",
        annotation_text="Median"
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
        use_container_width=True,
        key="forecast_error_distribution"
    )




    st.caption(
        "The histogram is limited to the 99th percentile "
        "for readability. Extreme errors remain preserved "
        "in the database and in the summary metrics."
    )


    maximum_error = float(
        verified_df[
            "AbsoluteError"
        ].max()
    )


    if maximum_error > p95_error:

        st.warning(
            f"""
            **Extreme forecast error detected**

            The maximum absolute error is
            **{maximum_error:.4f}**, compared with a
            95th-percentile error of **{p95_error:.4f}**.

            Review the underlying indicator, denominator,
            target, and reported actual before interpreting
            this observation as model failure.
            """
        )

# ==================================================
# DATA PREPARATION
# ==================================================

numeric_archive_columns = [
    "PredictedValue",
    "ActualValue",
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


verified_df = (
    archive_df[
        archive_df["ForecastStatus"]
        .eq("Verified")
    ]
    .dropna(
        subset=[
            "PredictedValue",
            "ActualValue",
            "AbsoluteError"
        ]
    )
    .copy()
)


pending_df = archive_df[
    archive_df["ForecastStatus"]
    .eq("Pending Actual")
].copy()


# ==================================================
# ADDITIONAL KPI CARDS
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Overview"
)


pending_count = len(pending_df)


p90_error = (
    float(
        metrics_row["P90AbsoluteError"]
    )
    if not metrics_df.empty
    else float("nan")
)


p95_error = (
    float(
        metrics_row["P95AbsoluteError"]
    )
    if not metrics_df.empty
    else float("nan")
)


zero_error_forecasts = (
    int(
        metrics_row["ZeroErrorForecasts"]
    )
    if not metrics_df.empty
    else 0
)


overview1, overview2, overview3, overview4 = (
    st.columns(4)
)


overview1.metric(
    "Pending Actuals",
    f"{pending_count:,}"
)


overview2.metric(
    "90th Percentile Error",
    f"{p90_error:.4f}"
)


overview3.metric(
    "95th Percentile Error",
    f"{p95_error:.4f}"
)


overview4.metric(
    "Exact Forecasts",
    f"{zero_error_forecasts:,}"
)


st.info(
    """
    This dashboard presents a historical Naive Persistence
    backtest on the Original Achievement Ratio scale.

    The 3,915 verified forecasts represent historical
    current-quarter to next-quarter comparisons. They are
    different from the 756 held-out test observations used
    for formal model comparison in the Model Performance
    Dashboard.
    """
)


# ==================================================
# FORECAST STATUS BREAKDOWN
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Status"
)


status_counts = (
    archive_df[
        "ForecastStatus"
    ]
    .fillna("Unknown")
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
        "Verified": "#2E7D32",
        "Pending Actual": "#F9A825",
        "Baseline": "#607D8B",
        "Unknown": "#9E9E9E"
    }
)


status_chart.update_traces(
    textposition="inside",
    textinfo="label+percent+value"
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
    use_container_width=True,
    key="forecast_status_pie"
)


# ==================================================
# ERROR DISTRIBUTION
# ==================================================

st.divider()

st.subheader(
    "Absolute Forecast Error Distribution"
)


if verified_df.empty:

    st.warning(
        "No verified forecasts are available."
    )

else:

    distribution_limit = (
        verified_df[
            "AbsoluteError"
        ]
        .quantile(0.99)
    )


    distribution_df = verified_df[
        verified_df["AbsoluteError"]
        .le(distribution_limit)
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
            verified_df[
                "AbsoluteError"
            ].median()
        ),
        line_dash="dash",
        line_color="#2E7D32",
        annotation_text="Median"
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
        use_container_width=True,
        key="project_scorecard_chart"
    )


    st.caption(
        "The histogram is limited to the 99th percentile "
        "for readability. Extreme errors remain preserved "
        "in the database and in the summary metrics."
    )


    maximum_error = float(
        verified_df[
            "AbsoluteError"
        ].max()
    )


    if maximum_error > p95_error:

        st.warning(
            f"""
            **Extreme forecast error detected**

            The maximum absolute error is
            **{maximum_error:.4f}**, compared with a
            95th-percentile error of **{p95_error:.4f}**.

            Review the underlying indicator, denominator,
            target, and reported actual before interpreting
            this observation as model failure.
            """
        )
# ==================================================
# PROJECT VERIFICATION SCORECARD
# ==================================================

st.divider()

st.subheader(
    "Project Forecast Verification Scorecard"
)


project_numeric_columns = [
    "VerifiedForecasts",
    "MeanAbsoluteError",
    "MedianAbsoluteError",
    "RootMeanSquaredError",
    "MaximumAbsoluteError"
]


for column in project_numeric_columns:

    if column in project_df.columns:

        project_df[column] = pd.to_numeric(
            project_df[column],
            errors="coerce"
        )


project_scorecard = (
    project_df
    .sort_values(
        [
            "MedianAbsoluteError",
            "MeanAbsoluteError"
        ]
    )
    .copy()
)


project_scorecard = project_scorecard.rename(
    columns={
        "ProjectID": "Project",
        "VerifiedForecasts":
            "Verified Forecasts",
        "MeanAbsoluteError":
            "Mean Absolute Error",
        "MedianAbsoluteError":
            "Median Absolute Error",
        "RootMeanSquaredError":
            "RMSE",
        "MaximumAbsoluteError":
            "Maximum Absolute Error"
    }
)


display_project_columns = [
    column
    for column in [
        "Project",
        "Verified Forecasts",
        "Mean Absolute Error",
        "Median Absolute Error",
        "RMSE",
        "Maximum Absolute Error",
        "DatasetType",
        "Model",
        "Version"
    ]
    if column in project_scorecard.columns
]


st.dataframe(
    project_scorecard[
        display_project_columns
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "Mean Absolute Error":
            st.column_config.NumberColumn(
                "Mean Absolute Error",
                format="%.4f"
            ),
        "Median Absolute Error":
            st.column_config.NumberColumn(
                "Median Absolute Error",
                format="%.4f"
            ),
        "RMSE":
            st.column_config.NumberColumn(
                "RMSE",
                format="%.4f"
            ),
        "Maximum Absolute Error":
            st.column_config.NumberColumn(
                "Maximum Absolute Error",
                format="%.4f"
            )
    }
)


if not project_df.empty:

    project_chart_df = (
        project_df
        .sort_values(
            "MedianAbsoluteError"
        )
    )


    project_chart = px.bar(
        project_chart_df,
        x="ProjectID",
        y="MedianAbsoluteError",
        hover_data=[
            "VerifiedForecasts",
            "MeanAbsoluteError",
            "RootMeanSquaredError",
            "MaximumAbsoluteError"
        ],
        labels={
            "ProjectID": "Project",
            "MedianAbsoluteError":
                "Median Absolute Error"
        }
    )


    project_chart.update_layout(
        xaxis_title=None,
        margin=dict(
            l=10,
            r=10,
            t=20,
            b=10
        )
    )


    st.plotly_chart(
        project_chart,
        use_container_width=True,
        key="project_verfication_scorecard"
    )


# ==================================================
# FORECAST VERIFICATION EXPLORER
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Explorer"
)


project_options = sorted(
    archive_df["ProjectID"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


selected_projects = st.multiselect(
    "Project",
    options=project_options,
    default=[]
)


explorer_df = archive_df.copy()


if selected_projects:

    explorer_df = explorer_df[
        explorer_df["ProjectID"]
        .astype(str)
        .isin(selected_projects)
    ]


indicator_options = sorted(
    explorer_df["IndicatorID"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


selected_indicators = st.multiselect(
    "Indicator",
    options=indicator_options,
    default=[]
)


if selected_indicators:

    explorer_df = explorer_df[
        explorer_df["IndicatorID"]
        .astype(str)
        .isin(selected_indicators)
    ]


status_options = sorted(
    explorer_df["ForecastStatus"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


selected_statuses = st.multiselect(
    "Forecast Status",
    options=status_options,
    default=[
        status
        for status in [
            "Verified"
        ]
        if status in status_options
    ]
)


if selected_statuses:

    explorer_df = explorer_df[
        explorer_df["ForecastStatus"]
        .astype(str)
        .isin(selected_statuses)
    ]


explorer_df = explorer_df.sort_values(
    [
        "ProjectID",
        "IndicatorID",
        "ForecastOriginIndex"
    ]
)


explorer_columns = [
    column
    for column in [
        "ProjectID",
        "IndicatorID",
        "Model",
        "Version",
        "DatasetType",
        "EvaluationType",
        "ForecastOriginPeriod",
        "ForecastTargetPeriod",
        "PredictedValue",
        "ActualValue",
        "SignedError",
        "AbsoluteError",
        "ForecastStatus"
    ]
    if column in explorer_df.columns
]


st.write(
    f"Forecast records displayed: "
    f"{len(explorer_df):,}"
)


st.dataframe(
    explorer_df[
        explorer_columns
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "PredictedValue":
            st.column_config.NumberColumn(
                "Predicted Value",
                format="%.4f"
            ),
        "ActualValue":
            st.column_config.NumberColumn(
                "Actual Value",
                format="%.4f"
            ),
        "SignedError":
            st.column_config.NumberColumn(
                "Signed Error",
                format="%.4f"
            ),
        "AbsoluteError":
            st.column_config.NumberColumn(
                "Absolute Error",
                format="%.4f"
            )
    }
)

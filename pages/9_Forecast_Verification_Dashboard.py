import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.database_utils import DB_FILE


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Forecast Verification Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title(
    "📈 Forecast Verification Dashboard"
)

st.caption(
    "Evaluate historical forecast accuracy, compare Original "
    "and Capped analytical tracks, inspect project-level "
    "performance, and review formal held-out model results."
)


# ============================================================
# PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>
    .track-card {
        background-color: #F6F9FC;
        border-left: 6px solid #1F4E78;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .original-card {
        background-color: #EEF5FB;
        border-left: 6px solid #1F4E78;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .capped-card {
        background-color: #EFF8F0;
        border-left: 6px solid #2E7D32;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .section-note {
        color: #64748B;
        font-size: 0.92rem;
        margin-top: -0.4rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DATABASE HELPERS
# ============================================================

def table_exists(
    connection,
    table_name
):

    result = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
     *  WHERE type = 'table'
          A*D name = ?
        """,
        (
*           table_name,
        )
 *  ).fetchone()[0]

    return bool*
        result
    )


@st.cache_*ata(
    ttl=60
)
def load_data():*
    connection = sqlite3.connect(*        DB_FILE
    )

    try:

 *      if not table_exists(
       *    connection,
            "predi*tion_archive"
        ):

        *   raise RuntimeError(
           *    "The prediction_archive table *oes not exist."
            )

   *    archive = pd.read_sql_query(
 *          """
            SELECT **            FROM prediction_archiv*
            """,
            conn*ction
        )

        if table_*xists(
            connection,
   *        "model_performance"
      * ):

            performance = pd.*ead_sql_query(
                """*                SELECT *
         *      FROM model_performance
     *          """,
                con*ection
            )

        else*

            performance = pd.Dat*Frame()

        if table_exists(
*           connection,
           *"model_recommendation"
        ):
*            recommendations = pd.r*ad_sql_query(
                """
*               SELECT *
          *     FROM model_recommendation
   *            """,
                c*nnection
            )

        el*e:

            recommendations = *d.DataFrame()

    finally:

     *  connection.close()

    return (*        archive,
        performan*e,
        recommendations
    )

*# ================================*===========================
# LOAD*DATA
# ===========================*================================

*ry:

    (
        archive_df,
   *    performance_df,
        recomm*ndation_df
    ) = load_data()

ex*ept Exception as error:

    st.er*or(
        "Forecast-verification*data could not be loaded."
    )

*   st.exception(
        error
   *)

    st.stop()


if archive_df.e*pty:

    st.warning(
        "The*prediction archive contains no rec*rds."
    )

    st.stop()


# ===*==================================*=====================
# REQUIRED C*LUMN VALIDATION
# ================*==================================*========

required_archive_columns*= [
    "ProjectID",
    "IndicatorID",
    "PredictedValue",
    "ActualValue",
    "ForecastStatus"
]
*
missing_archive_columns = [
    column
    for column in required_archive_columns
    if column not in archive_df.columns
]


if missing_a*chive_columns:

    st.error(
    *   "The prediction archive is miss*ng required columns: "
        + "* ".join(
            missing_archi*e_columns
        )
    )

    st.*top()


# ========================*==================================*
# NORMALIZE ANALYTICAL TRACK
# ==*==================================*======================

if "Datase*Type" not in archive_df.columns:

*   archive_df[
        "DatasetType"
    ] = "Original"


archive_df[
    "DatasetType"
] = (
    archive_df[
        "DatasetType"
    ]
    .fillna("Original")
    .astype(str)
    .str.strip()
    .str.title()
)


available_tracks = sorted(
    archive_df[
        "DatasetType"
    ]
    .dropna()
    .unique()
    .tolist()
)


# ============================================================
# TRACK SELECTOR
# ============================================================

st.divider()

st.subheader(
    "Analytical Track"
)

st.markdown(
    """
    <div class="section-note">
        Select the analytical scale used throughout the
        forecast-verification dashboard.
    </div>
    """,
    unsafe_allow_html=True
)


selected_track = st.radio(
    "Select dataset",
    options=[
        "Original",
        "Capped"
    ],
    horizontal=True,
    key="forecast_verification_track"
)


if selected_track == "Original":

    st.markdown(
        """
        <div class="original-card">
            <strong>Original Analytical Track</strong><br><br>
            Displays forecast verification using the original,
            uncapped Achievement Ratio scale. Extreme values are
            retained exactly as represented in the prediction archive.
        </div>
        """,
        unsafe_allow_html=True
    )

else:

    st.markdown(
        """
        <div class="capped-card">
            <strong>Capped Analytical Track</strong><br><br>
            Displays forecast verification using the capped
            Achievement Ratio scale. Ratios are limited to 3.0
            within the Capped analytical pipeline.
        </div>
        """,
        unsafe_allow_html=True
    )


track_archive_df = archive_df[
    archive_df[
        "DatasetType"
    ].eq(
        selected_track
    )
].copy()


if track_archive_df.empty:

    st.warning(
        f"No {selected_track} forecast-verification records "
        "currently exist in prediction_archive."
    )

    st.info(
        "The selector is working correctly, but historical "
        f"{selected_track} predictions must first be written "
        "to prediction_archive before verification charts, "
        "project scorecards, and explorer records can be shown."
    )

    st.write(
        "Analytical tracks currently available in "
        "prediction_archive:"
    )

    st.write(
        available_tracks
    )

    if (
        not performance_df.empty
        and
        "DatasetType" in performance_df.columns
    ):

        formal_track_results = performance_df[
            performance_df[
                "DatasetType"
            ]
            .astype(str)
            .str.strip()
            .str.title()
            .eq(
                selected_track
            )
        ].copy()

        if not formal_track_results.empty:

            st.subheader(
                f"{selected_track} Formal Model Evaluation"
            )

            st.info(
                "These are formal held-out model-comparison "
                "results, not historical prediction-archive "
                "verification records."
            )

            formal_columns = [
                column
                for column in [
                    "Model",
                    "DatasetType",
                    "TestRows",
                    "MAE",
                    "RMSE",
                    "GovernanceRank",
                    "IsRecommended",
                    "SelectionRule",
                    "EvaluationDate"
                ]
                if column in formal_track_results.columns
            ]

            if "GovernanceRank" in formal_track_results.columns:

                formal_track_results = (
                    formal_track_results
                    .sort_values(
                        "GovernanceRank"
                    )
                )

            st.dataframe(
                formal_track_results[
                    formal_columns
                ],
                hide_index=True,
                use_container_width=True
            )

    st.stop()


# ============================================================
# NUMERIC PREPARATION
# ============================================================

numeric_archive_columns = [
    "PredictedValue",
    "ActualValue",
    "SignedError",
    "AbsoluteError",
    "SquaredError",
    "ForecastOriginIndex"
]


for column in numeric_archive_columns:

    if column in track_archive_df.columns:

        track_archive_df[
            column
        ] = pd.to_numeric(
            track_archive_df[
                column
            ],
            errors="coerce"
        )


# Recalculate missing error columns consistently.

if "SignedError" not in track_archive_df.columns:

    track_archive_df[
        "SignedError"
    ] = (
        track_archive_df[
            "PredictedValue"
        ]
        -
        track_archive_df[
            "ActualValue"
        ]
    )


if "AbsoluteError" not in track_archive_df.columns:

    track_archive_df[
        "AbsoluteError"
    ] = track_archive_df[
        "SignedError"
    ].abs()


if "SquaredError" not in track_archive_df.columns:

    track_archive_df[
        "SquaredError"
    ] = (
        track_archive_df[
            "SignedError"
        ]
        ** 2
    )


verified_df = (
    track_archive_df[
        track_archive_df[
            "ForecastStatus"
        ]
        .astype(str)
        .str.strip()
        .eq(
            "Verified"
        )
    ]
    .dropna(
        subset=[
            "PredictedValue",
            "ActualValue",
            "AbsoluteError",
            "SquaredError"
        ]
    )
    .copy()
)


pending_df = track_archive_df[
    track_archive_df[
        "ForecastStatus"
    ]
    .astype(str)
    .str.strip()
    .eq(
        "Pending Actual"
    )
].copy()


# ============================================================
# DYNAMIC TRACK METRICS
# ============================================================

verified_count = len(
    verified_df
)


pending_count = len(
    pending_df
)


if verified_df.empty:

    mae = np.nan
    median_error = np.nan
    rmse = np.nan
    p90_error = np.nan
    p95_error = np.nan
    maximum_error = np.nan
    zero_error_forecasts = 0

else:

    mae = float(
        verified_df[
            "AbsoluteError"
        ].mean()
    )

    median_error = float(
        verified_df[
            "AbsoluteError"
        ].median()
    )

    rmse = float(
        np.sqrt(
            verified_df[
                "SquaredError"
            ].mean()
        )
    )

    p90_error = float(
        verified_df[
            "AbsoluteError"
        ].quantile(
            0.90
        )
    )

    p95_error = float(
        verified_df[
            "AbsoluteError"
        ].quantile(
            0.95
        )
    )

    maximum_error = float(
        verified_df[
            "AbsoluteError"
        ].max()
    )

    zero_error_forecasts = int(
        verified_df[
            "AbsoluteError"
        ]
        .fillna(np.inf)
        .abs()
        .le(
            1e-12
        )
        .sum()
    )


# ============================================================
# KPI SECTION
# ============================================================

st.divider()

st.subheader(
    f"{selected_track} Forecast Verification Summary"
)


kpi1, kpi2, kpi3, kpi4 = st.columns(4)


kpi1.metric(
    "Verified Forecasts",
    f"{verified_count:,}"
)


kpi2.metric(
    "MAE",
    (
        f"{mae:.4f}"
        if pd.notna(mae)
        else "N/A"
    )
)


kpi3.metric(
    "Median Absolute Error",
    (
        f"{median_error:.4f}"
        if pd.notna(median_error)
        else "N/A"
    )
)


kpi4.metric(
    "RMSE",
    (
        f"{rmse:.4f}"
        if pd.notna(rmse)
        else "N/A"
    )
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
    (
        f"{p90_error:.4f}"
        if pd.notna(p90_error)
        else "N/A"
    )
)


overview3.metric(
    "95th Percentile Error",
    (
        f"{p95_error:.4f}"
        if pd.notna(p95_error)
        else "N/A"
    )
)


overview4.metric(
    "Exact Forecasts",
    f"{zero_error_forecasts:,}"
)


st.info(
    f"""
    This section presents historical forecast verification
    for the **{selected_track} analytical track**.

    Historical prediction-archive verification is different
    from the 756 held-out observations used for formal
    four-model comparison in the Model Performance Dashboard.
    """
)


# ============================================================
# FORMAL HELD-OUT MODEL COMPARISON
# ============================================================

st.divider()

st.subheader(
    f"{selected_track} Formal Model Comparison"
)

st.markdown(
    """
    <div class="section-note">
        Formal temporal test results used for model ranking and
        governance recommendation. These results are separate
        from the historical rolling forecast archive.
    </div>
    """,
    unsafe_allow_html=True
)


if (
    performance_df.empty
    or
    "DatasetType" not in performance_df.columns
):

    st.info(
        "Formal model-performance results are not available."
    )

else:

    comparison_df = performance_df[
        performance_df[
            "DatasetType"
        ]
        .astype(str)
        .str.strip()
        .str.title()
        .eq(
            selected_track
        )
    ].copy()

    if comparison_df.empty:

        st.info(
            f"No formal model-performance results exist "
            f"for the {selected_track} track."
        )

    else:

        numeric_performance_columns = [
            "TestRows",
            "MAE",
            "RMSE",
            "MAE_Rank",
            "RMSE_Rank",
            "GovernanceRank",
            "IsRecommended"
        ]

        for column in numeric_performance_columns:

            if column in comparison_df.columns:

                comparison_df[
                    column
                ] = pd.to_numeric(
                    comparison_df[
                        column
                    ],
                    errors="coerce"
                )

        if "GovernanceRank" in comparison_df.columns:

            comparison_df = comparison_df.sort_values(
                "GovernanceRank"
            )

        comparison_columns = [
            column
            for column in [
                "Model",
                "DatasetType",
                "TestRows",
                "MAE",
                "RMSE",
                "MAE_Rank",
                "RMSE_Rank",
                "GovernanceRank",
                "IsRecommended",
                "SelectionRule",
                "EvaluationDate"
            ]
            if column in comparison_df.columns
        ]

        st.dataframe(
            comparison_df[
                comparison_columns
            ],
            hide_index=True,
            use_container_width=True,
            column_config={
                "MAE":
                    st.column_config.NumberColumn(
                        "MAE",
                        format="%.6f"
                    ),

                "RMSE":
                    st.column_config.NumberColumn(
                        "RMSE",
                        format="%.6f"
                    )
            }
        )

        recommended_rows = comparison_df.copy()

        if "IsRecommended" in recommended_rows.columns:

            recommended_rows = recommended_rows[
                recommended_rows[
                    "IsRecommended"
                ]
                .fillna(0)
                .eq(1)
            ]

        if (
            recommended_rows.empty
            and
            "GovernanceRank" in comparison_df.columns
        ):

            recommended_rows = comparison_df[
                comparison_df[
                    "GovernanceRank"
                ].eq(1)
            ]

        if not recommended_rows.empty:

            recommended_model = str(
                recommended_rows.iloc[0][
                    "Model"
                ]
            )

            st.success(
                f"Recommended model for the "
                f"{selected_track} track: "
                f"**{recommended_model}**"
            )

        chart_columns_available = all(
            column in comparison_df.columns
            for column in [
                "Model",
                "MAE",
                "RMSE"
            ]
        )

        if chart_columns_available:

            comparison_chart_df = (
                comparison_df[
                    [
                        "Model",
                        "MAE",
                        "RMSE"
                    ]
                ]
                .melt(
                    id_vars=[
                        "Model"
                    ],
                    value_vars=[
                        "MAE",
                        "RMSE"
                    ],
                    var_name="Metric",
                    value_name="Error"
                )
            )

            comparison_chart = px.bar(
                comparison_chart_df,
                x="Model",
                y="Error",
                color="Metric",
                barmode="group",
                labels={
                    "Model":
                        "Forecasting Model",

                    "Error":
                        "Error Value"
                }
            )

            comparison_chart.update_layout(
                margin=dict(
                    l=10,
                    r=10,
                    t=20,
                    b=10
                )
            )

            st.plotly_chart(
                comparison_chart,
                use_container_width=True,
                key=(
                    "formal_model_comparison_"
                    + selected_track.lower()
                )
            )


# ============================================================
# FORECAST STATUS BREAKDOWN
# ============================================================

st.divider()

st.subheader(
    f"{selected_track} Forecast Verification Status"
)


status_counts = (
    track_archive_df[
        "ForecastStatus"
    ]
    .fillna("Unknown")
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

        "Baseline":
            "#607D8B",

        "Unknown":
            "#9E9E9E"
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
    key=(
        "forecast_status_"
        + selected_track.lower()
    )
)


# ============================================================
# ERROR DISTRIBUTION
# ============================================================

st.divider()

st.subheader(
    f"{selected_track} Absolute Forecast Error Distribution"
)


if verified_df.empty:

    st.warning(
        f"No verified {selected_track} forecasts are available."
    )

else:

    distribution_limit = verified_df[
        "AbsoluteError"
    ].quantile(
        0.99
    )

    distribution_df = verified_df[
        verified_df[
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
        x=median_error,
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
        key=(
            "error_distribution_"
            + selected_track.lower()
        )
    )

    st.caption(
        "The histogram is limited to the 99th percentile "
        "for readability. Extreme forecast errors remain "
        "preserved in the database and summary metrics."
    )

    if (
        pd.notna(maximum_error)
        and
        pd.notna(p95_error)
        and
        maximum_error > p95_error
    ):

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


# ============================================================
# PROJECT VERIFICATION SCORECARD
# ============================================================

st.divider()

st.subheader(
    f"{selected_track} Project Forecast Verification Scorecard"
)


if verified_df.empty:

    st.info(
        "No verified records are available for project scoring."
    )

else:

    project_scorecard = (
        verified_df
        .groupby(
            "ProjectID",
            dropna=False
        )
        .agg(
            VerifiedForecasts=(
                "AbsoluteError",
                "size"
            ),

            MeanAbsoluteError=(
                "AbsoluteError",
                "mean"
            ),

            MedianAbsoluteError=(
                "AbsoluteError",
                "median"
            ),

            RootMeanSquaredError=(
                "SquaredError",
                lambda values: float(
                    np.sqrt(
                        values.mean()
                    )
                )
            ),

            MaximumAbsoluteError=(
                "AbsoluteError",
                "max"
            )
        )
        .reset_index()
        .sort_values(
            [
                "MedianAbsoluteError",
                "MeanAbsoluteError"
            ]
        )
    )

    project_scorecard[
        "DatasetType"
    ] = selected_track

    st.dataframe(
        project_scorecard,
        hide_index=True,
        use_container_width=True,
        column_config={
            "ProjectID":
                st.column_config.TextColumn(
                    "Project"
                ),

            "VerifiedForecasts":
                st.column_config.NumberColumn(
                    "Verified Forecasts",
                    format="%d"
                ),

            "MeanAbsoluteError":
                st.column_config.NumberColumn(
                    "Mean Absolute Error",
                    format="%.4f"
                ),

            "MedianAbsoluteError":
                st.column_config.NumberColumn(
                    "Median Absolute Error",
                    format="%.4f"
                ),

            "RootMeanSquaredError":
                st.column_config.NumberColumn(
                    "RMSE",
                    format="%.4f"
                ),

            "MaximumAbsoluteError":
                st.column_config.NumberColumn(
                    "Maximum Absolute Error",
                    format="%.4f"
                )
        }
    )

    project_chart = px.bar(
        project_scorecard,
        x="ProjectID",
        y="MedianAbsoluteError",
        hover_data=[
            "VerifiedForecasts",
            "MeanAbsoluteError",
            "RootMeanSquaredError",
            "MaximumAbsoluteError"
        ],
        labels={
            "ProjectID":
                "Project",

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
        key=(
            "project_scorecard_"
            + selected_track.lower()
        )
    )


# ============================================================
# FORECAST VERIFICATION EXPLORER
# ============================================================

st.divider()

st.subheader(
    f"{selected_track} Forecast Verification Explorer"
)


project_options = sorted(
    track_archive_df[
        "ProjectID"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


selected_projects = st.multiselect(
    "Project",
    options=project_options,
    default=[],
    key=(
        "project_filter_"
        + selected_track.lower()
    )
)


explorer_df = track_archive_df.copy()


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


indicator_options = sorted(
    explorer_df[
        "IndicatorID"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


selected_indicators = st.multiselect(
    "Indicator",
    options=indicator_options,
    default=[],
    key=(
        "indicator_filter_"
        + selected_track.lower()
    )
)


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


status_options = sorted(
    explorer_df[
        "ForecastStatus"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


default_statuses = [
    status
    for status in [
        "Verified"
    ]
    if status in status_options
]


selected_statuses = st.multiselect(
    "Forecast Status",
    options=status_options,
    default=default_statuses,
    key=(
        "status_filter_"
        + selected_track.lower()
    )
)


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


sort_columns = [
    column
    for column in [
        "ProjectID",
        "IndicatorID",
        "ForecastOriginIndex"
    ]
    if column in explorer_df.columns
]


if sort_columns:

    explorer_df = explorer_df.sort_values(
        sort_columns
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
    "Forecast records displayed: "
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


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Historical forecast verification and formal held-out "
    "model comparison are presented separately to preserve "
    "analytical clarity and governance transparency."
)

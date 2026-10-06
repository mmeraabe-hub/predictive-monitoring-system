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
    "Dynamic forecasting performance using the latest retraining results."
)


# ==================================================
# LOAD DATA
# ==================================================

@st.cache_data(ttl=60)
def load_data():

    conn = sqlite3.connect(DB_FILE)

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
            """,
            conn
        )

        registry = pd.read_sql_query(
            """
            SELECT *
            FROM model_registry
            """,
            conn
        )



prediction_archive = pd.read_sql_query(
    """
    SELECT *
    FROM prediction_archive
    """,
    conn
)

registry = pd.read_sql_query(
    """
    SELECT *
    FROM model_registry
    """,
    conn
)
 

    finally:

        conn.close()

    return (
        verification_metrics,
        project_metrics,
        prediction_archive,
        registry
    )


try:

    (
        metrics_df,
        project_df,
        archive_df,
        registry_df
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
# FORECAST VERIFICATION OVERVIEW
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Overview"
)

original_model = performance_df[
    (
        performance_df["DatasetType"]
        == "Original"
    )
    &
    (
        performance_df["IsRecommended"]
        == 1
    )
]

capped_model = performance_df[
    (
        performance_df["DatasetType"]
        == "Capped"
    )
    &
    (
        performance_df["IsRecommended"]
        == 1
    )
]

forecast_col1, forecast_col2 = st.columns(2)

with forecast_col1:

    st.info("🎯 ORIGINAL FORECAST CHAMPION")

    if not original_model.empty:

        model = original_model.iloc[0]

        st.markdown(
            f"### **{model['Model']}**"
        )

        metric1, metric2, metric3 = st.columns(3)

        metric1.metric(
            "Test Rows",
            int(model["TestRows"])
        )

        metric2.metric(
            "MAE",
            round(
                float(model["MAE"]),
                4
            )
        )

        metric3.metric(
            "RMSE",
            round(
                float(model["RMSE"]),
                4
            )
        )

with forecast_col2:

    st.success("🏆 CAPPED FORECAST CHAMPION")

    if not capped_model.empty:

        model = capped_model.iloc[0]

        st.markdown(
            f"### **{model['Model']}**"
        )

        metric1, metric2, metric3 = st.columns(3)

        metric1.metric(
            "Test Rows",
            int(model["TestRows"])
        )

        metric2.metric(
            "MAE",
            round(
                float(model["MAE"]),
                4
            )
        )

        metric3.metric(
            "RMSE",
            round(
                float(model["RMSE"]),
                4
            )
        )
# ==================================================
# FORECAST VERIFICATION STATUS
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Status"
)

status_df = performance_df.copy()

status_df[
    "RecommendationStatus"
] = status_df[
    "IsRecommended"
].map(
    {
        1: "Champion",
        0: "Candidate"
    }
)

status_counts = (
    status_df[
        "RecommendationStatus"
    ]
    .value_counts()
    .rename_axis(
        "RecommendationStatus"
    )
    .reset_index(
        name="Models"
    )
)

status_chart = px.pie(
    status_counts,
    names="RecommendationStatus",
    values="Models",
    hole=0.45,
    color="RecommendationStatus",
    color_discrete_map={
        "Champion": "#2E7D32",
        "Candidate": "#90A4AE"
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
    width="stretch"
)

st.caption(
    "Champion models are currently selected for production. "
    "Candidate models were evaluated but not selected."
)

# ==================================================
# ERROR DISTRIBUTION
# ==================================================

st.divider()

st.subheader(
    "Model Error Distribution"
)

error_df = performance_df.melt(
    id_vars=[
        "Model",
        "DatasetType"
    ],
    value_vars=[
        "MAE",
        "RMSE"
    ],
    var_name="Metric",
    value_name="Error"
)

error_chart = px.bar(
    error_df,
    x="Model",
    y="Error",
    color="Metric",
    barmode="group"
)

st.plotly_chart(
    error_chart,
    width="stretch"
)


# ==================================================
# PROJECT FORECAST SCORECARD
# ==================================================

st.divider()

st.subheader(
    "Project Forecast Scorecard"
)

if "Project" in dashboard_df.columns:

    scorecard = (
        dashboard_df
        .groupby(
            "Project"
        )
        .size()
        .reset_index(
            name="ProductionRows"
        )
    )

    st.dataframe(
        scorecard,
        width="stretch",
        hide_index=True
    )


# ==================================================
# FORECAST EXPLORER
# ==================================================

st.divider()

st.subheader(
    "Forecast Verification Explorer"
)

st.dataframe(
    performance_df,
    width="stretch",
    hide_index=True
)
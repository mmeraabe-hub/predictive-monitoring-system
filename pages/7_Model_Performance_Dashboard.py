import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.database_utils import DB_FILE


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Model Performance & Governance",
    page_icon="🤖",
    layout="wide"
)


st.title(
    "Model Performance & Governance Dashboard"
)


st.caption(
    "Compare forecasting performance on Original and "
    "Capped Achievement Ratio datasets and review the "
    "current model recommendation."
)


st.info(
    """
    **How to interpret this dashboard**

    Models are compared only within the selected target scale.

    - **Original** preserves the observed Achievement Ratio.
    - **Capped** limits the Achievement Ratio to the sensitivity cap.
    - The recommended model is selected using the lowest RMSE.
    - MAE is used as the secondary metric.
    """
)


# ==================================================
# LOAD MODEL DATA
# ==================================================

@st.cache_data
def load_model_performance():

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        performance = pd.read_sql_query(
            """
            SELECT *
            FROM model_performance
            """,
            conn
        )

        recommendations = pd.read_sql_query(
            """
            SELECT *
            FROM model_recommendation
            """,
            conn
        )

    finally:

        conn.close()

    return (
        performance,
        recommendations
    )


try:

    model_data, recommendation_data = (
        load_model_performance()
    )

except Exception as error:

    st.error(
        "The model-performance tables could not be loaded."
    )

    st.exception(error)

    st.stop()


if model_data.empty:

    st.warning(
        "No model-performance records are available."
    )

    st.stop()


# ==================================================
# VALIDATE REQUIRED COLUMNS
# ==================================================

required_columns = [
    "DatasetType",
    "Model",
    "TargetScale",
    "TestRows",
    "MAE",
    "RMSE",
    "GovernanceRank",
    "IsRecommended",
    "SelectionRule"
]


missing_columns = [
    column
    for column in required_columns
    if column not in model_data.columns
]


if missing_columns:

    st.error(
        "Required model-performance columns are missing: "
        + ", ".join(missing_columns)
    )

    st.stop()


numeric_columns = [
    "TestRows",
    "MAE",
    "RMSE",
    "MAE_Rank",
    "RMSE_Rank",
    "GovernanceRank"
]


for column in numeric_columns:

    if column in model_data.columns:

        model_data[column] = pd.to_numeric(
            model_data[column],
            errors="coerce"
        )


# ==================================================
# SIDEBAR FILTER
# ==================================================

st.sidebar.header(
    "Model Evaluation Filters"
)


available_dataset_types = (
    model_data["DatasetType"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


preferred_order = [
    dataset_type
    for dataset_type in [
        "Original",
        "Capped"
    ]
    if dataset_type in available_dataset_types
]


remaining_types = [
    dataset_type
    for dataset_type in available_dataset_types
    if dataset_type not in preferred_order
]


dataset_options = (
    preferred_order
    + sorted(remaining_types)
)


selected_dataset = st.sidebar.radio(
    "Achievement Ratio Dataset",
    options=dataset_options,
    index=0
)


st.sidebar.caption(
    "Switch between Original and Capped results. "
    "Models are ranked only within the selected dataset."
)


# ==================================================
# FILTER SELECTED DATASET
# ==================================================

selected_models = (
    model_data[
        model_data["DatasetType"]
        .eq(selected_dataset)
    ]
    .copy()
)


selected_models = selected_models.sort_values(
    [
        "GovernanceRank",
        "RMSE",
        "MAE"
    ]
)


if selected_models.empty:

    st.warning(
        "No models are available for the selected dataset."
    )

    st.stop()


selected_recommendation = (
    recommendation_data[
        recommendation_data["DatasetType"]
        .eq(selected_dataset)
    ]
    .copy()
)


if selected_recommendation.empty:

    selected_recommendation = (
        selected_models[
            selected_models["GovernanceRank"]
            .eq(1)
        ]
        .copy()
    )


recommended_row = (
    selected_recommendation
    .sort_values(
        [
            "RMSE",
            "MAE"
        ]
    )
    .iloc[0]
)


recommended_model = str(
    recommended_row["Model"]
)


recommended_mae = float(
    recommended_row["MAE"]
)


recommended_rmse = float(
    recommended_row["RMSE"]
)


test_rows = int(
    recommended_row["TestRows"]
)


target_scale = str(
    recommended_row["TargetScale"]
)


# ==================================================
# SELECTED DATASET SUMMARY
# ==================================================

st.subheader(
    f"{selected_dataset} Dataset Evaluation"
)


st.caption(
    f"Target scale: {target_scale}"
)


kpi1, kpi2, kpi3, kpi4 = st.columns(4)


kpi1.metric(
    "Recommended Model",
    recommended_model
)


kpi2.metric(
    "Recommended MAE",
    f"{recommended_mae:.4f}"
)


kpi3.metric(
    "Recommended RMSE",
    f"{recommended_rmse:.4f}"
)


kpi4.metric(
    "Test Observations",
    f"{test_rows:,}"
)


# ==================================================
# RECOMMENDATION EXPLANATION
# ==================================================

st.success(
    f"""
    **Current recommendation: {recommended_model}**

    This model currently ranks first for the
    **{selected_dataset}** dataset using the governance rule:
    **lowest RMSE, then lowest MAE**.

    The recommendation is data-driven and can change after
    future model retraining and evaluation.
    """
)


# ==================================================
# MODEL RANKING TABLE
# ==================================================

st.divider()


st.subheader(
    "Model Performance Ranking"
)


ranking_table = selected_models[
    [
        "GovernanceRank",
        "Model",
        "MAE",
        "RMSE",
        "MAE_Rank",
        "RMSE_Rank",
        "TestRows",
        "IsRecommended"
    ]
].copy()


ranking_table = ranking_table.rename(
    columns={
        "GovernanceRank": "Governance Rank",
        "MAE_Rank": "MAE Rank",
        "RMSE_Rank": "RMSE Rank",
        "TestRows": "Test Rows",
        "IsRecommended": "Recommended"
    }
)


ranking_table["Recommendation"] = (
    ranking_table["Recommended"]
    .apply(
        lambda value:
        "✅ Recommended"
        if bool(value)
        else "Alternative"
    )
)


ranking_table = ranking_table.drop(
    columns=[
        "Recommended"
    ]
)


st.dataframe(
    ranking_table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "MAE": st.column_config.NumberColumn(
            "MAE",
            format="%.4f"
        ),
        "RMSE": st.column_config.NumberColumn(
            "RMSE",
            format="%.4f"
        )
    }
)


# ==================================================
# PERFORMANCE VISUALIZATIONS
# ==================================================

st.divider()


left_chart, right_chart = st.columns(2)


with left_chart:

    st.subheader(
        "MAE Comparison"
    )

    mae_chart = px.bar(
        selected_models,
        x="Model",
        y="MAE",
        color="IsRecommended",
        color_discrete_map={
            True: "#2E7D32",
            False: "#90A4AE"
        },
        labels={
            "MAE": "Mean Absolute Error",
            "Model": "Forecasting Model"
        }
    )

    mae_chart.update_layout(
        showlegend=False,
        xaxis_title=None,
        margin=dict(
            l=10,
            r=10,
            t=20,
            b=10
        )
    )

    st.plotly_chart(
        mae_chart,
        use_container_width=True
    )


with right_chart:

    st.subheader(
        "RMSE Comparison"
    )

    rmse_chart = px.bar(
        selected_models,
        x="Model",
        y="RMSE",
        color="IsRecommended",
        color_discrete_map={
            True: "#2E7D32",
            False: "#90A4AE"
        },
        labels={
            "RMSE": "Root Mean Squared Error",
            "Model": "Forecasting Model"
        }
    )

    rmse_chart.update_layout(
        showlegend=False,
        xaxis_title=None,
        margin=dict(
            l=10,
            r=10,
            t=20,
            b=10
        )
    )

    st.plotly_chart(
        rmse_chart,
        use_container_width=True
    )


# ==================================================
# GOVERNANCE & INTERPRETATION
# ==================================================

st.divider()


st.subheader(
    "Model Governance"
)


governance1, governance2 = st.columns(2)


with governance1:

    st.markdown(
        """
        ### Selection Method

        **Primary metric**

        RMSE is used as the primary selection metric because
        it gives greater weight to larger forecast errors.

        **Secondary metric**

        MAE is used as the secondary metric because it
        represents the average absolute forecast error.

        **Recommended model**

        The model with the lowest RMSE is recommended.
        MAE is used if additional differentiation is needed.
        """
    )


with governance2:

    st.markdown(
        f"""
        ### Current Evaluation Context

        **Dataset type:** {selected_dataset}

        **Target scale:** {target_scale}

        **Test observations:** {test_rows:,}

        **Models evaluated:** {len(selected_models)}

        **Current recommendation:** {recommended_model}

        Original and Capped error values should be interpreted
        within their own target scales rather than compared
        directly across scales.
        """
    )


# ==================================================
# FUTURE MODEL CANDIDATES
# ==================================================

with st.expander(
    "🔬 Future Models and Retraining Governance"
):

    st.markdown(
        """
        ### Candidate Models for Future Evaluation

        Additional models may be considered when sufficient
        longitudinal data becomes available:

        - LightGBM
        - CatBoost
        - Histogram Gradient Boosting
        - Elastic Net
        - Time-series methods where reporting history and
          periodicity are sufficient

        ### Retraining Governance

        The current recommendation should not be treated as a
        permanent winner.

        After new ITT data is entered:

        1. Re-run the transformation pipeline.
        2. Preserve the chronological train/test design.
        3. Retrain all approved candidate models.
        4. Recalculate MAE and RMSE on the same test records.
        5. Refresh the SQLite model-performance tables.
        6. Review the recommendation before promoting a model.

        New models should only be recommended after they have
        been trained and evaluated using the same validation
        framework as the existing models.
        """
    )


# ==================================================
# FOOTNOTE
# ==================================================

st.caption(
    "Model recommendations support decision-making and "
    "should be reviewed together with data quality, sample "
    "coverage, operational context, and professional judgement."
)

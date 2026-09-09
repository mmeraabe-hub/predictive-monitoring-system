import sqlite3
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.database_utils import DB_FILE

# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Model Lifecycle & Drift Monitoring",
    page_icon="🔄",
    layout="wide"
)

st.title(
    "Model Lifecycle & Drift Monitoring Dashboard"
)

st.caption(
    "Track model versions, production status, quarterly reviews, and model drift."
)

st.info(
    """
    Quarterly retraining governance is enabled.

    Models are reviewed every 3 months.
    Retraining review does not automatically promote a model.
    Candidate models must still pass governance review.
    """
)
# ==================================================
# LOAD TABLES
# ==================================================

@st.cache_data
def load_lifecycle_data():

    conn = sqlite3.connect(DB_FILE)

    try:

        registry = pd.read_sql_query(
            """
            SELECT *
            FROM model_registry
            """,
            conn
        )

        drift = pd.read_sql_query(
            """
            SELECT *
            FROM model_drift_history
            """,
            conn
        )

    finally:

        conn.close()

    return registry, drift


try:

    registry_data, drift_data = load_lifecycle_data()

except Exception as error:

    st.error(
        "The model lifecycle tables could not be loaded."
    )

    st.exception(error)

    st.stop()
    # ==================================================
# QUARTERLY REVIEW CALCULATIONS
# ==================================================

registry_data["TrainingDate"] = pd.to_datetime(
    registry_data["TrainingDate"]
)

registry_data["NextReviewDate"] = (
    registry_data["TrainingDate"]
    + pd.DateOffset(months=3)
)

today = pd.Timestamp(date.today())

registry_data["DaysUntilReview"] = (
    registry_data["NextReviewDate"]
    - today
).dt.days


def review_status(days):

    if days < 0:
        return "Overdue"

    if days <= 30:
        return "Due Soon"

    return "Scheduled"


registry_data["ReviewStatus"] = (
    registry_data["DaysUntilReview"]
    .apply(review_status)
)
# ==================================================
# EXECUTIVE KPIS
# ==================================================

production_models = int(
    registry_data["Status"]
    .eq("Production")
    .sum()
)

candidate_models = int(
    registry_data["Status"]
    .eq("Candidate")
    .sum()
)

versions_tracked = int(
    registry_data["Version"]
    .nunique()
)

drift_alerts = int(
    drift_data["DriftFlag"]
    .astype(str)
    .str.lower()
    .eq("yes")
    .sum()
)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Production Models",
    production_models
)

col2.metric(
    "Candidate Models",
    candidate_models
)

col3.metric(
    "Versions",
    versions_tracked
)

col4.metric(
    "Drift Alerts",
    drift_alerts
)
# ==================================================
# CURRENT PRODUCTION MODELS
# ==================================================

st.divider()

st.subheader(
    "Current Production Models"
)

production_models_df = (
    registry_data[
        registry_data["Status"]
        == "Production"
    ]
)

st.dataframe(
    production_models_df[
        [
            "DatasetType",
            "Model",
            "Version",
            "TrainingDate",
            "MAE",
            "RMSE"
        ]
    ],
    use_container_width=True,
    hide_index=True
)
# ==================================================
# MODEL REGISTRY
# ==================================================

st.divider()

st.subheader(
    "Model Registry"
)

st.dataframe(
    registry_data,
    use_container_width=True,
    hide_index=True
)
# ==================================================
# QUARTERLY REVIEW SCHEDULE
# ==================================================

st.divider()

st.subheader(
    "Quarterly Retraining Schedule"
)

review_table = (
    registry_data[
        [
            "DatasetType",
            "Model",
            "Version",
            "TrainingDate",
            "NextReviewDate",
            "DaysUntilReview",
            "ReviewStatus"
        ]
    ]
)

st.dataframe(
    review_table,
    use_container_width=True,
    hide_index=True
)
# ==================================================
# DRIFT MONITORING
# ==================================================

st.divider()

st.subheader(
    "Model Drift History"
)

st.dataframe(
    drift_data,
    use_container_width=True,
    hide_index=True
)

drift_chart = px.bar(
    drift_data,
    x="Model",
    y="DriftPercent",
    color="DatasetType",
    barmode="group",
    title="RMSE Drift by Model"
)

st.plotly_chart(
    drift_chart,
    use_container_width=True
)
# ==================================================
# GOVERNANCE RULES
# ==================================================

st.divider()

st.subheader(
    "Lifecycle Governance Rules"
)

st.markdown(
    """
### Quarterly Retraining Policy

- Review Frequency: Every 3 Months
- Primary Metric: RMSE
- Secondary Metric: MAE
- Production Selection Rule: Lowest RMSE
- Candidate models require review before promotion

### Current Production Models

- Original Dataset → Naive Persistence
- Capped Dataset → Random Forest

### Future Lifecycle Workflow

1. Upload new ITT
2. Refresh SQLite
3. Quarterly Review Trigger
4. Retrain Candidate Models
5. Compare MAE / RMSE
6. Calculate Drift
7. Register New Version
8. Promote Approved Model
"""
)


import streamlit as st
st.set_page_config(
    page_title="Predictive Monitoring System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        ont-weight: 700;
        color: #1F4E78;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1.05rem;
        color: #5F6B76;
        margin-bottom: 1.5rem;
    }
    .info-card {
        background-color: #F6F9FC;
        border-left: 5px solid #1F4E78;
        padding: 1.1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .footer-note {
        color: #6B7280;
        font-size: 0.85rem;
        margin-top: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown(
    '<div class="main-title">'
    'AI-Enabled Predictive Monitoring and Learning System'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'An integrated platform for predictive analytics, governance, '
    'lifecycle management, automation, and organizational learning'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="info-card">
    <strong>Platform Overview</strong><br>
    This platform transforms traditional Indicator Tracking Table (ITT)
    reporting into a governed, predictive, and automated Monitoring,
    Evaluation, and Learning (MEL) environment.

    The system supports the complete monitoring lifecycle including
    data acquisition, review and approval, longitudinal transformation,
    predictive analytics, model governance, lifecycle management,
    and automation monitoring.
    </div>
    """,
    unsafe_allow_html=True
)

st.subheader("Monitoring, Analytics, Governance and Automation Lifecycle")

st.code(
"""
Upload ITT
      ↓
Quality Review
      ↓
Approval
      ↓
ETL / UPSERT
      ↓
Longitudinal Data Transformation
      ↓
Feature Engineering
      ↓
Forecast Model Training
      ↓
Model Testing and Evaluation
      ↓
Governance Recommendation
      ↓
Lifecycle Management
      ↓
Automation Monitoring
"""
)

st.divider()

st.subheader("Core Platform Capabilities")

st.markdown(
"""
✅ Upload and manage Indicator Tracking Tables (ITTs)

✅ Review data quality and approve datasets

✅ Perform ETL and UPSERT processing

✅ Transform monitoring data into longitudinal analytical datasets

✅ Generate predictive forecasts using multiple forecasting models

✅ Support forecast verification and model evaluation

✅ Provide risk classification and early-warning monitoring

✅ Maintain model registries and governance records

✅ Support candidate evaluation and recommendation workflows

✅ Monitor model drift and governance readiness

✅ Manage model lifecycle decisions including promotion and decline

✅ Track champion models and rollback readiness

✅ Execute retraining and governance automation workflows

✅ Monitor automation history and audit trails
"""
)

st.divider()

st.subheader("Forecasting Framework")

st.markdown(
"""
The platform supports a governed forecasting framework based on
longitudinal project monitoring data and engineered analytical variables.

Forecasting candidates include:

- Naive Persistence
- Linear Regression
- Random Forest
- XGBoost

Models are evaluated using governance criteria and recommendation rules
to identify suitable candidates for lifecycle review and monitoring.
"""
)

st.divider()

st.subheader("Governance and Lifecycle Management")

st.markdown(
"""
The governance framework supports:

- Model Registry Management
- Candidate Evaluation
- Governance Recommendations
- Drift Monitoring
- Champion Model Tracking
- Lifecycle Decisions
- Rollback Readiness Assessment
"""
)

st.divider()

st.subheader("Automation Services")

st.markdown(
"""
Automation services support:

- Retraining Engine
- Governance Preview Engine
- Automation Orchestrator
- Automation Logger
- Automation Monitoring Dashboard

These services improve operational transparency,
auditability, and governance oversight.
"""
)

st.warning(
    "Forecasts, recommendations, governance results, and risk classifications "
    "are decision-support outputs and should be reviewed by MEL, program, "
    "and governance stakeholders before operational action."
)

st.markdown(
    '<div class="footer-note">'
    'Developed as part of a Master\'s project on AI-enabled predictive '
    'monitoring, governance, automation, and organizational learning.'
    '</div>',
    unsafe_allow_html=True
)

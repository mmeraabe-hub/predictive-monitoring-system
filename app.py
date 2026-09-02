
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
    'AI-Enabled Predictive Monitoring and Early Warning System'
    '</div>',
    unsafe_allow_html=True
)
st.markdown(
    '<div class="subtitle">'
    'Quarterly, annual, and life-of-project monitoring for '
    'development project indicators'
    '</div>',
    unsafe_allow_html=True
)
st.markdown(
    """
    <div class="info-card">
    <strong>Purpose</strong><br>
    This prototype transforms project ITT data into forward-looking
    monitoring information. It supports quarterly monitoring,
    annual trajectory assessment, life-of-project forecasting,
    and early warning classification.
    </div>
    """,
    unsafe_allow_html=True
)
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Short-Term Monitoring")
    st.write(
        "Compare quarterly actual achievement with the "
        "corresponding quarterly target."
    )
    st.info(
        "Primary output: Quarter achievement percentage "
        "and Quarter Status"
    )
with col2:
    st.subheader("Medium-Term Monitoring")
    st.write(
        "Assess current annual progress and estimate the "
        "year-end achievement ratio."
    )
    st.info(
        "Primary output: Annual Forecast Ratio, "
        "Annual Progress Gap, and Annual Status"
    )
with col3:
    st.subheader("Long-Term Monitoring")
    st.write(
        "Assess cumulative progress and projected performance "
        "against the life-of-project target."
    )
    st.info(
        "Primary output: LoP Forecast Ratio, "
        "LoP Progress Gap, and LoP Status"
    )
st.divider()
st.subheader("Prototype Modules")
st.markdown(
    """
    1. **Portfolio Dashboard**
        Executive overview of projects, indicators, and risk status.
    2. **Project Dashboard**
        Detailed monitoring of each project and its priority indicators.
    3. **Indicator Dashboard**
        Quarterly, annual, and LoP performance with trend visualizations.
    4. **Create and Update ITT**
        Create projects and indicators and enter quarterly data periodically.
    5. **Upload Existing ITT**
        Import an existing standardized Excel ITT.
    """
)
st.warning(
    "Forecasts and risk classifications are decision-support signals. "
    "They should be reviewed by MEL and program staff before management action."
)
st.markdown(
    '<div class="footer-note">'
    'Prototype developed for an academic project on predictive '
    'monitoring and adaptive learning.'
    '</div>',
    unsafe_allow_html=True
)

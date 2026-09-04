%%writefile pages/3_Indicator_Dashboard.py
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_utils import (
    load_dashboard_data,
    prepare_numeric_columns,
)

from utils.risk_thresholds import classify_risk


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Indicator Dashboard",
    page_icon="🎯",
    layout="wide",
)


# ==================================================
# PROFESSIONAL STYLE
# ==================================================

st.markdown(
    """
    <style>
    .page-title {
        color: #1F4E78;
        font-size: 2.1rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }

    .page-subtitle {
        color: #64748B;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .summary-box {
        background-color: #F7FAFC;
        border-left: 5px solid #1F4E78;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .insight-box {
        background-color: #F6F9FC;
        border-left: 5px solid #4472C4;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.8rem;
    }

    .method-note {
        background-color: #FFF8E1;
        border-left: 5px solid #F9A825;
        border-radius: 8px;
        padding: 0.9rem;
        margin-top: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="page-title">'
    'Indicator Performance Dashboard'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="page-subtitle">'
    'Detailed quarterly, annual, and '
    'life-of-project indicator monitoring'
    '</div>',
    unsafe_allow_html=True,
)


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def safe_percentage(value):

    if pd.isna(value):
        return "No Data"

    return f"{float(value):.1%}"


def safe_number(value):

    if pd.isna(value):
        return "No Data"

    return f"{float(value):,.1f}"


def safe_classify(value, assessment_level):

    if pd.isna(value):
        return "Unknown"

    return classify_risk(
        float(value),
        assessment_level,
    )


def status_icon(status):

    icons = {
        "On Track": "🟢",
        "At Risk": "🟡",
        "Off Track": "🔴",
        "Unknown": "⚪",
    }

    return icons.get(
        status,
        "⚪",
    )


def dataframe_to_excel(dataframe):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Indicator_Data",
            index=False,
        )

    output.seek(0)

    return output.getvalue()


# ==================================================
# LOAD DATA
# ==================================================

try:

    data, selected_sheet, available_sheets = (
        load_dashboard_data()
    )

except Exception as error:

    st.error(
        "The monitoring dataset could not be loaded."
    )

    st.exception(error)
    st.stop()


data = prepare_numeric_columns(data)


required_columns = [
    "IndicatorID",
    "Project",
    "IndicatorName",
    "Year",
    "Quarter",
    "PeriodIndex",
    "PeriodLabel",
    "QuarterTarget",
    "QuarterActual",
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


# ==================================================
# SIDEBAR FILTERS
# ==================================================

st.sidebar.header("Indicator Filters")

st.sidebar.caption(
    "Nothing is selected automatically. "
    "Choose a project and indicator to begin."
)


# --------------------------------------------------
# PROJECT SELECTION
# --------------------------------------------------

project_options = sorted(
    data["Project"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


selected_project = st.sidebar.selectbox(
    "Project",
    options=project_options,
    index=None,
    placeholder="Select a project",
)


if selected_project is None:

    st.info(
        "Select a project from the sidebar to view "
        "its available indicators."
    )

    project_summary = (
        data[
            [
                "Project",
                "IndicatorID",
            ]
        ]
        .dropna(
            subset=[
                "Project",
                "IndicatorID",
            ]
        )
        .groupby(
            "Project",
            as_index=False,
        )
        .agg(
            Indicators=(
                "IndicatorID",
                "nunique",
            )
        )
        .sort_values(
            "Project"
        )
    )

    st.subheader(
        "Available Projects"
    )

    st.dataframe(
        

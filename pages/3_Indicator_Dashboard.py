import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_utils import (
    load_dashboard_data,
    prepare_numeric_columns,
    get_indicator_history
)

from utils.status_logic import (
    classify_quarter_status,
    classify_forecast_status,
    status_icon
)


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Indicator Dashboard",
    page_icon="🎯",
    layout="wide"
)


# --------------------------------------------------
# PAGE STYLE
# --------------------------------------------------

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

    .profile-box {
        background-color: #F6F9FC;
        border-left: 5px solid #1F4E78;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .insight-card {
        background-color: #F6F9FC;
        border-left: 5px solid #4472C4;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
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
    unsafe_allow_html=True
)


st.markdown(
    '<div class="page-title">'
    'Indicator Performance Dashboard'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="page-subtitle">'
    'Quarterly, annual, and life-of-project monitoring'
    '</div>',
    unsafe_allow_html=True
)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

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
    "QuarterActual"
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


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.header("Indicator Selection")


project_options = sorted(
    data["Project"]
    .dropna()
    .astype(str)
    .unique()
)


if not project_options:

    st.error(
        "No projects are available in the dataset."
    )

    st.stop()


selected_project = st.sidebar.selectbox(
    "Project",
    project_options
)


project_data = data[
    data["Project"].astype(str)
    == selected_project
].copy()


indicator_lookup = (
    project_data[
        [
            "IndicatorID",
            "IndicatorName"
        ]
    ]
    .drop_duplicates(
        subset=["IndicatorID"]
    )
    .sort_values("IndicatorName")
)


indicator_labels = {
    (
        str(row["IndicatorID"])
        + " | "
        + str(row["IndicatorName"])
    ): row["IndicatorID"]

    for _, row in indicator_lookup.iterrows()
}


if not indicator_labels:

    st.error(
        "No indicators are available for this project."
    )

    st.stop()


selected_indicator_label = (
    st.sidebar.selectbox(
        "Indicator",
        list(indicator_labels.keys())
    )
)


selected_indicator_id = (
    indicator_labels[
        selected_indicator_label
    ]
)


indicator_data = project_data[
    project_data["IndicatorID"]
    == selected_indicator_id
].copy()


available_years = sorted(
    indicator_data["Year"]
    .dropna()
    .astype(int)
    .unique()
)


if not available_years:

    st.error(
        "No project years are available for this indicator."
    )

    st.stop()


selected_year = st.sidebar.selectbox(
    "Reporting Year",
    available_years,
    index=len(available_years) - 1
)


available_quarters = sorted(
    indicator_data.loc[
        indicator_data["Year"] == selected_year,
        "Quarter"
    ]
    .dropna()
    .astype(int)
    .unique()
)


if not available_quarters:

    available_quarters = [1, 2, 3, 4]


selected_quarter = st.sidebar.selectbox(
    "Reporting Quarter",
    available_quarters,
    index=len(available_quarters) - 1
)


selected_period = (
    ((int(selected_year) - 1) * 4)
    + int(selected_quarter)
)


history = get_indicator_history(
    data=data,
    indicator_id=selected_indicator_id,
    selected_period=selected_period
)


if history.empty:

    st.warning(
        "No observations are available for the selected "
        "indicator and reporting period."
    )

    st.stop()


history = (
    history
    .sort_values("PeriodIndex")
    .reset_index(drop=True)
)


current_record = history.iloc[-1]


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def safe_number(value, decimals=1):

    if pd.isna(value):
        return "No Data"

    return f"{value:,.{decimals}f}"


def safe_percentage(value):

    if pd.isna(value):
        return "No Data"

    return f"{value * 100:,.1f}%"


def progress_bar(value, label):

    st.write(label)

    if pd.isna(value):

        st.caption("No data available.")
        return

    displayed_value = min(
        max(float(value), 0.0),
        1.0
    )

    st.progress(displayed_value)

    st.caption(
        safe_percentage(value)
    )


def gap_text(value, horizon):

    if pd.isna(value):

        return (
            f"{horizon} progress gap cannot "
            "be calculated."
        )

    gap_percentage = abs(value * 100)

    if value > 0.02:

        return (
            f"{horizon} progress is "
            f"{gap_percentage:,.1f}% ahead of the "
            "expected time-based trajectory."
        )

    if value < -0.02:

        return (
            f"{horizon} progress is "
            f"{gap_percentage:,.1f}% behind the "
            "expected time-based trajectory."
        )

    return (
        f"{horizon} progress is broadly aligned with "
        "the expected time-based trajectory."
    )


def dataframe_to_excel(dataframe):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Indicator_History",
            index=False
        )

    output.seek(0)

    return output.getvalue()


def create_forecast_index_chart(
    dataframe,
    value_column,
    line_name,
    line_color
):

    chart_data = dataframe[
        [
            "PeriodIndex",
            "PeriodLabel",
            value_column
        ]
    ].copy()

    chart_data[value_column] = pd.to_numeric(
        chart_data[value_column],
        errors="coerce"
    )

    chart_data = (
        chart_data
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .dropna(
            subset=[value_column]
        )
        .sort_values("PeriodIndex")
    )


    chart = go.Figure()


    if chart_data.empty:

        return chart, chart_data


    maximum_value = chart_data[
        value_column
    ].max()


    upper_limit = max(
        1.20,
        float(maximum_value) * 1.10
    )


    chart.add_hrect(
        y0=0,
        y1=0.80,
        fillcolor="#FDECEC",
        opacity=0.50,
        line_width=0,
        annotation_text="Off Track",
        annotation_position="top left"
    )


    chart.add_hrect(
        y0=0.80,
        y1=1.00,
        fillcolor="#FFF8E1",
        opacity=0.55,
        line_width=0,
        annotation_text="At Risk

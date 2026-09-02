
import os
import pandas as pd
import numpy as np
CURRENT_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)
APP_FOLDER = os.path.dirname(
    CURRENT_FOLDER
)
DATA_FILE = os.path.join(
    APP_FOLDER,
    "data",
    "monitoring_data.xlsx"
)
def load_dashboard_data():
    """
    Load the full monitoring dataset.
    The function prefers detailed longitudinal sheets.
    If no preferred sheet exists, it uses the first sheet.
    """
    workbook = pd.ExcelFile(DATA_FILE)
    preferred_sheets = [
        "Longitudinal",
        "Full_Longitudinal",
        "Longitudinal_Data",
        "Sheet1"
    ]
    selected_sheet = None
    for sheet_name in preferred_sheets:
        if sheet_name in workbook.sheet_names:
            selected_sheet = sheet_name
            break
    if selected_sheet is None:
        selected_sheet = workbook.sheet_names[0]
    data = pd.read_excel(
        DATA_FILE,
        sheet_name=selected_sheet
    )
    return (
        data,
        selected_sheet,
        workbook.sheet_names
    )
def prepare_numeric_columns(data):
    """
    Convert monitoring values to numeric form safely.
    """
    data = data.copy()
    numeric_columns = [
        "LoPTarget",
        "Baseline",
        "Year",
        "Quarter",
        "PeriodIndex",
        "QuarterTarget",
        "QuarterActual",
        "AchievementRatio",
        "QuarterVariance",
        "CumulativeTarget",
        "CumulativeActual",
        "LoPProgress",
        "AnnualTarget",
        "CurrentYearActual",
        "AnnualProgress",
        "AnnualTimeProgress",
        "AnnualProgressGap",
        "AnnualForecastRatio",
        "CurrentProjectQuarter",
        "LoPTimeProgress",
        "LoPProgressGap",
        "LoPForecastRatio"
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
            )
        return data
def create_period_snapshot(
    data,
    year,
    quarter
):
    """
    Produce the latest available observation for each
    indicator up to the selected reporting period.
    """
    data = data.copy()
    selected_period = (
        ((int(year) - 1) * 4)
        + int(quarter)
    )
    eligible_data = data[
        data["PeriodIndex"] <= selected_period
    ].copy()
    snapshot = (
        eligible_data
        .sort_values(
            [
                "IndicatorID",
                "PeriodIndex"
            ]
        )
        .groupby(
            "IndicatorID",
            as_index=False
        )
        .tail(1)
        .reset_index(drop=True)
    )
    return snapshot
def get_indicator_history(
    data,
    indicator_id,
    selected_period=None
):
    """
    Return chronological history for one indicator.
    """
    history = data[
        data["IndicatorID"] == indicator_id
    ].copy()
    if selected_period is not None:
        history = history[
            history["PeriodIndex"]
            <= selected_period
        ].copy()
    history = history.sort_values(
"PeriodIndex"
    ).reset_index(drop=True)
    return history

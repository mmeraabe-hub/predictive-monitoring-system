
import pandas as pd


def classify_quarter_status(row):

    target = row.get("QuarterTarget")
    actual = row.get("QuarterActual")
    ratio = row.get("AchievementRatio")

    if pd.isna(target) or pd.isna(actual):
        return "No Data"

    if target == 0:
        return "Not Scheduled"

    if pd.isna(ratio):
        return "No Data"

    if ratio >= 1.0:
        return "On Track"

    if ratio >= 0.80:
        return "At Risk"

    return "Off Track"


def classify_forecast_status(value):

    if pd.isna(value):
        return "No Data"

    if value >= 1.0:
        return "On Track"

    if value >= 0.80:
        return "At Risk"

    return "Off Track"


def status_icon(status):

    icons = {
        "On Track": "🟢",
        "At Risk": "🟡",
        "Off Track": "🔴",
        "Not Scheduled": "⚪",
        "No Data": "⚪"
    }

    return icons.get(status, "⚪")


def status_color(status):

    colors = {
        "On Track": "#2E7D32",
        "At Risk": "#F9A825",
        "Off Track": "#C62828",
        "Not Scheduled": "#757575",
        "No Data": "#9E9E9E"
    }

    return colors.get(status, "#757575")

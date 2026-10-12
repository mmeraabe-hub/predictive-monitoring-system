import re
import sqlite3
from datetime import datetime

import pandas as pd


DATABASE_PATH = "predictive_monitoring.db"


def clean_text(value):
    """
    Convert blank values to None and clean valid text.
    """
    if pd.isna(value):
        return None

    cleaned_value = str(value).strip()

    if not cleaned_value:
        return None

    return cleaned_value


def clean_numeric(value):
    """
    Convert valid numeric values to float.

    Zero is preserved as a valid value.
    Blank and invalid values become None.
    """
    if pd.isna(value):
        return None

    if isinstance(value, str):
        cleaned_value = value.strip()

        if not cleaned_value:
            return None

        cleaned_value = cleaned_value.replace(",", "")

        try:
            return float(cleaned_value)

        except ValueError:
            return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def normalize_indicator_id(value):
    """
    Standardize an already approved Indicator ID without
    changing its established sequence.
    """
    indicator_id = clean_text(value)

    if indicator_id is None:
        return None

    indicator_id = indicator_id.replace("\\_", "_")
    indicator_id = indicator_id.replace(" ", "")

    return indicator_id.upper()


def derive_project_code(indicator_id):
    """
    Derive the project code from an established Indicator ID.

    Examples:
        GG_005 -> GG
        RFSA_016 -> RFSA
        CRRP_004 -> CRRP
        RA_010 -> RA
    """
    if indicator_id is None:
        return None

    match = re.match(
        r"^([A-Z][A-Z0-9]*)[_-]\d+$",
        indicator_id,
    )

    if match:
        return match.group(1)

    parts = re.split(
        r"[_-]",
        indicator_id,
        maxsplit=1,
    )

    if parts:
        return parts[0].strip().upper()

    return None


def get_project_duration(group):
    """
    Estimate the approved project duration from YearNumber.

    If YearNumber is unavailable, use the highest annual target
    year containing a value.
    """
    if "YearNumber" in group.columns:
        numeric_years = pd.to_numeric(
            group["YearNumber"],
            errors="coerce",
        ).dropna()

        valid_years = numeric_years[
            numeric_years.between(1, 5)
        ]

        if not valid_years.empty:
            return int(valid_years.max())

    annual_target_columns = [
        (5, "Year 5 target"),
        (5, "Year 5 Target"),
        (4, "Year 4 target"),
        (4, "Year 4 Target"),
        (3, "Year 3 Target"),
        (2, "Year 2 Target"),
        (1, "Year 1 Target"),
    ]

    for year_number, column_name in annual_target_columns:
        if column_name in group.columns:
            values = pd.to_numeric(
                group[column_name],
                errors="coerce",
            )

            if values.notna().any():
                return year_number

    return 1


def first_non_null(group, column_name):
    """
    Return the first non-null value from a grouped indicator.
    """
    if column_name not in group.columns:
        return None

    values = group[column_name].dropna()

    if values.empty:
        return None

    return values.iloc[0]


def get_annual_target(group, year_number):
    """
    Retrieve an annual target while handling the spacing and
    capitalization differences in existing database columns.
    """
    column_options = {
        1: [
            "Year 1 Target",
        ],
        2: [
            "Year 2 Target",
        ],
        3: [
            "Year 3 Target",
        ],
        4: [
            "Year 4 target",
            "Year 4 Target",
            " Year 4 target",
        ],
        5: [
            "Year 5 target",
            "Year 5 Target",
            " Year 5 target",
        ],
    }

    for column_name in column_options[year_number]:
        if column_name in group.columns:
            value = first_non_null(
                group,
                column_name,
            )

            numeric_value = clean_numeric(value)

            if numeric_value is not None:
                return numeric_value

    return None


def load_dashboard_data(connection):
    """
    Load the approved production monitoring data.
    """
    table_exists = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'dashboard_data'
        """
    ).fetchone()[0]

    if not table_exists:
        raise RuntimeError(
            "The dashboard_data table does not exist."
        )

    dashboard_data = pd.read_sql_query(
        """
        SELECT *
        FROM dashboard_data
        """,
        connection,
    )

    if dashboard_data.empty:
        raise RuntimeError(
            "The dashboard_data table is empty."
        )

    required_columns = [
        "IndicatorID",
        "Project",
        "IndicatorName",
    ]

    missing_columns = [
        column_name
        for column_name in required_columns
        if column_name not in dashboard_data.columns
    ]

    if missing_columns:
        raise RuntimeError(
            "dashboard_data is missing required columns: "
            + ", ".join(missing_columns)
        )

    return dashboard_data


def prepare_indicator_master(dashboard_data):
    """
    Create one master record for every approved indicator.
    """
    prepared_data = dashboard_data.copy()

    prepared_data["IndicatorID"] = prepared_data[
        "IndicatorID"
    ].apply(normalize_indicator_id)

    prepared_data = prepared_data[
        prepared_data["IndicatorID"].notna()
        & prepared_data["Project"].notna()
  ]
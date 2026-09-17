
"""
Read-only model governance preview utilities.

Phase 12B.2

This module prepares:
- proposed candidate model versions;
- candidate registry preview records;
- RMSE drift preview records;
- recommendation summaries.

The module performs SELECT queries only.
It does not write to SQLite.
It does not register candidates.
It does not promote or decline models.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# CONSTANTS
# ============================================================

REQUIRED_REGISTRY_COLUMNS = [
    "Model",
    "DatasetType",
    "Version",
    "TrainingDate",
    "TestRows",
    "MAE",
    "RMSE",
    "Status"
]


REQUIRED_PERFORMANCE_COLUMNS = [
    "AnalysisTrack",
    "Model",
    "TargetScale",
    "TestRows",
    "MAE",
    "RMSE",
    "MAE_Rank",
    "RMSE_Rank",
    "DatasetType",
    "GovernanceRank",
    "IsRecommended",
    "SelectionRule",
    "EvaluationDate"
]


REQUIRED_ENGINE_RESULT_COLUMNS = [
    "AnalysisTrack",
    "Model",
    "TargetScale",
    "TestRows",
    "MAE",
    "RMSE",
    "MAE_Rank",
    "RMSE_Rank",
    "DatasetType",
    "GovernanceRank",
    "IsRecommended",
    "SelectionRule",
    "EvaluationDate"
]


# ============================================================
# GENERAL VALIDATION
# ============================================================

def validate_dataframe_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    dataframe_name: str
) -> None:
    """
    Validate that a dataframe contains all required columns.
    """

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise KeyError(
            dataframe_name
            + " is missing required columns: "
            + ", ".join(missing_columns)
        )


def validate_database_file(
    database_file: str | Path
) -> Path:
    """
    Confirm that the SQLite database exists and is healthy.
    """

    database_path = Path(
        database_file
    )

    if not database_path.exists():
        raise FileNotFoundError(
            f"Database not found: {database_path}"
        )

    with sqlite3.connect(
        str(database_path)
    ) as connection:

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

    if str(integrity).lower() != "ok":
        raise RuntimeError(
            "SQLite integrity check failed: "
            + str(integrity)
        )

    return database_path


# ============================================================
# VERSION FUNCTIONS
# ============================================================

def normalize_version_number(
    version_value: Any
) -> float:
    """
    Convert labels such as v1.0 and v2.0 to numeric values.
    """

    version_text = str(
        version_value
    ).strip().lower()

    version_text = (
        version_text
        .replace(
            "version",
            ""
        )
        .replace(
            "v",
            ""
        )
        .strip()
    )

    try:
        return float(
            version_text
        )

    except ValueError:
        return 0.0


def next_candidate_version(
    registry_data: pd.DataFrame,
    dataset_type: str,
    model_name: str
) -> str:
    """
    Return the next major version for one model-track pair.

    Examples:
    - no existing version -> v1.0
    - highest is v1.0 -> v2.0
    - highest is v2.0 -> v3.0
    """

    validate_dataframe_columns(
        dataframe=registry_data,
        required_columns=[
            "DatasetType",
            "Model",
            "Version"
        ],
        dataframe_name="Registry data"
    )

    matching_versions = registry_data[
        registry_data[
            "DatasetType"
        ].astype(str).eq(
            str(dataset_type)
        )
        &
        registry_data[
            "Model"
        ].astype(str).eq(
            str(model_name)
        )
    ].copy()

    if matching_versions.empty:
        return "v1.0"

    numeric_versions = matching_versions[
        "Version"
    ].apply(
        normalize_version_number
    )

    highest_version = float(
        numeric_versions.max()
    )

    next_major_version = int(
        math.floor(
            highest_version
        )
    ) + 1

    return f"v{next_major_version}.0"


def latest_registered_version(
    registry_data: pd.DataFrame,
    dataset_type: str,
    model_name: str
):
    """
    Return the highest registered version for a model track.

    Returns None when the model-track pair is not registered.
    """

    validate_dataframe_columns(
        dataframe=registry_data,
        required_columns=[
            "DatasetType",
            "Model",
            "Version"
        ],
        dataframe_name="Registry data"
    )

    matching_rows = registry_data[
        registry_data[
            "DatasetType"
        ].astype(str).eq(
            str(dataset_type)
        )
        &
        registry_data[
            "Model"
        ].astype(str).eq(
            str(model_name)
        )
    ].copy()

    if matching_rows.empty:
        return None

    matching_rows[
        "_VersionNumber"
    ] = matching_rows[
        "Version"
    ].apply(
        normalize_version_number
    )

    matching_rows = matching_rows.sort_values(
        "_VersionNumber",
        ascending=False
    )

    return str(
        matching_rows.iloc[0][
            "Version"
        ]
    )


# ============================================================
# DATABASE BASELINE LOADING
# ============================================================

def load_governance_baseline(
    database_file: str | Path
) -> dict[str, pd.DataFrame]:
    """
    Load model registry and performance baseline records.

    This function performs SELECT queries only.
    """

    database_path = validate_database_file(
        database_file
    )

    with sqlite3.connect(
        str(database_path)
    ) as connection:

        registry_data = pd.read_sql_query(
            """
            SELECT
                Model,
                DatasetType,
                Version,
                TrainingDate,
                TestRows,
                MAE,
                RMSE,
                Status
            FROM model_registry
            """,
            connection
        )

        performance_data = pd.read_sql_query(
            """
            SELECT
                AnalysisTrack,
                Model,
                TargetScale,
                TestRows,
                MAE,
                RMSE,
                MAE_Rank,
                RMSE_Rank,
                DatasetType,
                GovernanceRank,
                IsRecommended,
                SelectionRule,
                EvaluationDate
            FROM model_performance
            """,
            connection
        )

    validate_dataframe_columns(
        dataframe=registry_data,
        required_columns=REQUIRED_REGISTRY_COLUMNS,
        dataframe_name="Registry data"
    )

    validate_dataframe_columns(
        dataframe=performance_data,
        required_columns=REQUIRED_PERFORMANCE_COLUMNS,
        dataframe_name="Performance data"
    )

    return {
        "Registry":
            registry_data,

        "Performance":
            performance_data
    }


# ============================================================
# CANDIDATE REGISTRY PREVIEW
# ============================================================

def create_candidate_registry_preview(
    evaluated_results: pd.DataFrame,
    registry_data: pd.DataFrame,
    training_date: str | None = None
) -> pd.DataFrame:
    """
    Create proposed Candidate records without inserting them.
    """

    validate_dataframe_columns(
        dataframe=evaluated_results,
        required_columns=REQUIRED_ENGINE_RESULT_COLUMNS,
        dataframe_name="Evaluated results"
    )

    validate_dataframe_columns(
        dataframe=registry_data,
        required_columns=REQUIRED_REGISTRY_COLUMNS,
        dataframe_name="Registry data"
    )

    if training_date is None:
        training_date = datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d"
        )

    candidate_rows = []

    for _, result_row in evaluated_results.iterrows():

        dataset_type = str(
            result_row[
                "DatasetType"
            ]
        )

        model_name = str(
            result_row[
                "Model"
            ]
        )

        candidate_rows.append(
            {
                "Model":
                    model_name,

                "DatasetType":
                    dataset_type,

                "Version":
                    next_candidate_version(
                        registry_data=registry_data,
                        dataset_type=dataset_type,
                        model_name=model_name
                    ),

                "TrainingDate":
                    str(
                        training_date
                    ),

                "TestRows":
                    int(
                        result_row[
                            "TestRows"
                        ]
                    ),

                "MAE":
                    float(
                        result_row[
                            "MAE"
                        ]
                    ),

                "RMSE":
                    float(
                        result_row[
                            "RMSE"
                        ]
                    ),

                "Status":
                    "Candidate"
            }
        )

    preview = pd.DataFrame(
        candidate_rows
    )

    preview = (
        preview
        .sort_values(
            [
                "DatasetType",
                "RMSE",
                "MAE",
                "Model"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    if len(preview) != len(evaluated_results):
        raise RuntimeError(
            "Candidate preview row count does not match "
            "the evaluated result row count."
        )

    return preview


# ============================================================
# DRIFT PREVIEW
# ============================================================

def get_previous_metric(
    performance_data: pd.DataFrame,
    dataset_type: str,
    model_name: str,
    metric_name: str
) -> float:
    """
    Return a baseline MAE or RMSE value.
    """

    if metric_name not in [
        "MAE",
        "RMSE"
    ]:
        raise ValueError(
            "metric_name must be MAE or RMSE."
        )

    validate_dataframe_columns(
        dataframe=performance_data,
        required_columns=[
            "DatasetType",
            "Model",
            metric_name
        ],
        dataframe_name="Performance data"
    )

    matching_rows = performance_data[
        performance_data[
            "DatasetType"
        ].astype(str).eq(
            str(dataset_type)
        )
        &
        performance_data[
            "Model"
        ].astype(str).eq(
            str(model_name)
        )
    ].copy()

    if matching_rows.empty:
        return float(
            "nan"
        )

    values = pd.to_numeric(
        matching_rows[
            metric_name
        ],
        errors="coerce"
    ).dropna()

    if values.empty:
        return float(
            "nan"
        )

    return float(
        values.iloc[0]
    )


def calculate_metric_change_percent(
    previous_value: float,
    current_value: float
) -> float:
    """
    Calculate percentage change from baseline to candidate.
    """

    if pd.isna(
        previous_value
    ):
        return float(
            "nan"
        )

    previous_value = float(
        previous_value
    )

    current_value = float(
        current_value
    )

    if previous_value == 0.0:
        return float(
            "nan"
        )

    change_percent = (
        (
            current_value
            - previous_value
        )
        / abs(
            previous_value
        )
    ) * 100.0

    return float(
        change_percent
    )


def classify_drift(
    drift_percent: float,
    review_threshold_percent: float = 10.0
) -> str:
    """
    Classify drift using absolute RMSE percentage change.
    """

    if pd.isna(
        drift_percent
    ):
        return "No Baseline"

    if abs(
        float(
            drift_percent
        )
    ) > float(
        review_threshold_percent
    ):
        return "Review Required"

    return "No"


def create_drift_preview(
    evaluated_results: pd.DataFrame,
    performance_data: pd.DataFrame,
    registry_data: pd.DataFrame,
    candidate_preview: pd.DataFrame,
    evaluation_date: str | None = None,
    review_threshold_percent: float = 10.0
) -> pd.DataFrame:
    """
    Compare module results with the existing RMSE baseline.

    No model_drift_history record is inserted.
    """

    validate_dataframe_columns(
        dataframe=evaluated_results,
        required_columns=REQUIRED_ENGINE_RESULT_COLUMNS,
        dataframe_name="Evaluated results"
    )

    validate_dataframe_columns(
        dataframe=performance_data,
        required_columns=REQUIRED_PERFORMANCE_COLUMNS,
        dataframe_name="Performance data"
    )

    validate_dataframe_columns(
        dataframe=registry_data,
        required_columns=REQUIRED_REGISTRY_COLUMNS,
        dataframe_name="Registry data"
    )

    validate_dataframe_columns(
        dataframe=candidate_preview,
        required_columns=REQUIRED_REGISTRY_COLUMNS,
        dataframe_name="Candidate preview"
    )

    if evaluation_date is None:
        evaluation_date = datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d"
        )

    drift_rows = []

    for _, result_row in evaluated_results.iterrows():

        dataset_type = str(
            result_row[
                "DatasetType"
            ]
        )

        model_name = str(
            result_row[
                "Model"
            ]
        )

        candidate_match = candidate_preview[
            candidate_preview[
                "DatasetType"
            ].astype(str).eq(
                dataset_type
            )
            &
            candidate_preview[
                "Model"
            ].astype(str).eq(
                model_name
            )
        ].copy()

        if len(candidate_match) != 1:
            raise RuntimeError(
                "Expected exactly one candidate preview for "
                f"{dataset_type} / {model_name}, but found "
                f"{len(candidate_match)}."
            )

        previous_version = latest_registered_version(
            registry_data=registry_data,
            dataset_type=dataset_type,
            model_name=model_name
        )

        current_version = str(
            candidate_match.iloc[0][
                "Version"
            ]
        )

        previous_rmse = get_previous_metric(
            performance_data=performance_data,
            dataset_type=dataset_type,
            model_name=model_name,
            metric_name="RMSE"
        )

        current_rmse = float(
            result_row[
                "RMSE"
            ]
        )

        drift_percent = calculate_metric_change_percent(
            previous_value=previous_rmse,
            current_value=current_rmse
        )

        if (
            pd.notna(
                drift_percent
            )
            and abs(
                float(
                    drift_percent
                )
            ) < 0.000001
        ):
            drift_percent = 0.0

        drift_rows.append(
            {
                "EvaluationDate":
                    str(
                        evaluation_date
                    ),

                "Model":
                    model_name,

                "DatasetType":
                    dataset_type,

                "PreviousRMSE":
                    previous_rmse,

                "CurrentRMSE":
                    current_rmse,

                "DriftPercent":
                    drift_percent,

                "DriftFlag":
                    classify_drift(
                        drift_percent=drift_percent,
                        review_threshold_percent=(
                            review_threshold_percent
                        )
                    ),

                "PreviousVersion":
                    previous_version,

                "CurrentVersion":
                    current_version
            }
        )

    preview = pd.DataFrame(
        drift_rows
    )

    preview = (
        preview
        .sort_values(
            [
                "DatasetType",
                "CurrentRMSE",
                "Model"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    if len(preview) != len(evaluated_results):
        raise RuntimeError(
            "Drift preview row count does not match "
            "the evaluated result row count."
        )

    return preview


# ============================================================
# RECOMMENDATION SUMMARY
# ============================================================

def create_recommendation_preview(
    evaluated_results: pd.DataFrame
) -> pd.DataFrame:
    """
    Return one recommended model per evaluated dataset.
    """

    validate_dataframe_columns(
        dataframe=evaluated_results,
        required_columns=REQUIRED_ENGINE_RESULT_COLUMNS,
        dataframe_name="Evaluated results"
    )

    recommendation_preview = (
        evaluated_results[
            evaluated_results[
                "IsRecommended"
            ].eq(
                1
            )
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )

    recommendation_counts = (
        recommendation_preview
        .groupby(
            "DatasetType"
        )
        .size()
    )

    if not recommendation_counts.eq(
        1
    ).all():
        raise RuntimeError(
            "Each dataset type must have exactly one "
            "recommended model."
        )

    return recommendation_preview


# ============================================================
# COMPLETE GOVERNANCE PREVIEW PIPELINE
# ============================================================

def create_governance_previews(
    database_file: str | Path,
    evaluated_results: pd.DataFrame,
    training_date: str | None = None,
    evaluation_date: str | None = None,
    review_threshold_percent: float = 10.0
) -> dict[str, Any]:
    """
    Create all governance previews without database changes.
    """

    database_path = validate_database_file(
        database_file
    )

    baseline = load_governance_baseline(
        database_path
    )

    candidate_preview = create_candidate_registry_preview(
        evaluated_results=evaluated_results,
        registry_data=baseline[
            "Registry"
        ],
        training_date=training_date
    )

    drift_preview = create_drift_preview(
        evaluated_results=evaluated_results,
        performance_data=baseline[
            "Performance"
        ],
        registry_data=baseline[
            "Registry"
        ],
        candidate_preview=candidate_preview,
        evaluation_date=evaluation_date,
        review_threshold_percent=(
            review_threshold_percent
        )
    )

    recommendation_preview = create_recommendation_preview(
        evaluated_results
    )

    return {
        "Status":
            "Completed",

        "ReadOnly":
            True,

        "DatabaseFile":
            str(
                database_path
            ),

        "CandidateRegistryPreview":
            candidate_preview,

        "DriftPreview":
            drift_preview,

        "RecommendationPreview":
            recommendation_preview,

        "DatabaseWritesPerformed":
            False,

        "AutomaticPromotionPerformed":
            False
    }


__all__ = [
    "normalize_version_number",
    "next_candidate_version",
    "latest_registered_version",
    "load_governance_baseline",
    "create_candidate_registry_preview",
    "get_previous_metric",
    "calculate_metric_change_percent",
    "classify_drift",
    "create_drift_preview",
    "create_recommendation_preview",
    "create_governance_previews"
]

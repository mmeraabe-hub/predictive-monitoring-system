
"""
Reusable model retraining engine.

Phase 12B

This module reproduces the validated Original and Capped
model-comparison methodology used by the predictive monitoring
system.

The initial Phase 12B version is read-only:
- it loads dashboard_data;
- prepares chronological train and test datasets;
- retrains approved models;
- evaluates MAE and RMSE;
- generates governance recommendations;
- performs no SQLite writes;
- performs no automatic model promotion.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)

try:
    from xgboost import XGBRegressor

except ImportError as import_error:
    raise ImportError(
        "xgboost is required by the retraining engine. "
        "Install the project requirements before running "
        "model retraining."
    ) from import_error


# ============================================================
# ENGINE CONFIGURATION
# ============================================================

DEFAULT_TRAINING_SHARE = 0.80

DEFAULT_RANDOM_STATE = 42

SUPPORTED_DATASET_TYPES = (
    "Original",
    "Capped"
)

MODEL_NAMES = (
    "Naive Persistence",
    "Linear Regression",
    "Random Forest",
    "XGBoost"
)


TRACK_CONFIGURATIONS = {
    "Original": {
        "AnalysisTrack":
            "Primary: Original Ratio",

        "TargetScale":
            "Original Achievement Ratio",

        "CurrentColumn":
            "A_CurrentAR",

        "Lag1Column":
            "A_Lag1",

        "Lag2Column":
            "A_Lag2",

        "TargetColumn":
            "A_NextQuarterAR",

        "Features": [
            "A_CurrentAR",
            "A_Lag1",
            "A_Lag2",
            "QuarterNumber",
            "YearNumber"
        ]
    },

    "Capped": {
        "AnalysisTrack":
            "Sensitivity: Capped at 3",

        "TargetScale":
            "Capped Achievement Ratio",

        "CurrentColumn":
            "B_CurrentAR",

        "Lag1Column":
            "B_Lag1",

        "Lag2Column":
            "B_Lag2",

        "TargetColumn":
            "B_NextQuarterAR",

        "Features": [
            "B_CurrentAR",
            "B_Lag1",
            "B_Lag2",
            "QuarterNumber",
            "YearNumber"
        ]
    }
}


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def validate_database(
    database_file: str | Path
) -> Dict[str, Any]:
    """
    Validate the SQLite database and dashboard_data table.

    Returns database integrity and source-data counts.
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
    ) as conn:

        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        table_exists = conn.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'dashboard_data'
            """
        ).fetchone()[0]

        if not table_exists:
            raise RuntimeError(
                "dashboard_data was not found in the database."
            )

        production_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM dashboard_data
                """
            ).fetchone()[0]
        )

        unique_indicators = int(
            conn.execute(
                """
                SELECT COUNT(
                    DISTINCT IndicatorID
                )
                FROM dashboard_data
                """
            ).fetchone()[0]
        )

    if str(
        integrity
    ).lower() != "ok":
        raise RuntimeError(
            "SQLite integrity check failed: "
            f"{integrity}"
        )

    return {
        "DatabaseFile":
            str(
                database_path
            ),

        "SQLiteIntegrity":
            str(
                integrity
            ),

        "ProductionRows":
            production_rows,

        "UniqueIndicators":
            unique_indicators
    }


def load_dashboard_data(
    database_file: str | Path
) -> pd.DataFrame:
    """
    Load dashboard_data from the supplied SQLite database.
    """

    database_path = Path(
        database_file
    )

    validate_database(
        database_path
    )

    with sqlite3.connect(
        str(database_path)
    ) as conn:

        data = pd.read_sql_query(
            """
            SELECT *
            FROM dashboard_data
            """,
            conn
        )

    if data.empty:
        raise RuntimeError(
            "dashboard_data contains no records."
        )

    return data


# ============================================================
# DATA VALIDATION
# ============================================================

def required_columns_for_tracks(
    dataset_types: Tuple[str, ...]
) -> list:
    """
    Return the unique columns required by selected tracks.
    """

    required_columns = [
        "IndicatorID",
        "Project",
        "IndicatorName",
        "Year",
        "Quarter",
        "PeriodIndex",
        "QuarterNumber",
        "YearNumber"
    ]

    for dataset_type in dataset_types:

        if dataset_type not in TRACK_CONFIGURATIONS:
            raise ValueError(
                "Unsupported dataset type: "
                f"{dataset_type}"
            )

        configuration = TRACK_CONFIGURATIONS[
            dataset_type
        ]

        required_columns.extend(
            configuration[
                "Features"
            ]
        )

        required_columns.append(
            configuration[
                "TargetColumn"
            ]
        )

    return list(
        dict.fromkeys(
            required_columns
        )
    )


def validate_source_data(
    data: pd.DataFrame,
    dataset_types: Tuple[str, ...]
) -> Dict[str, Any]:
    """
    Validate columns and business keys before retraining.
    """

    required_columns = required_columns_for_tracks(
        dataset_types
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        raise KeyError(
            "Required retraining columns are missing: "
            + ", ".join(
                missing_columns
            )
        )

    business_keys = [
        "IndicatorID",
        "Year",
        "Quarter"
    ]

    null_business_keys = int(
        data[
            business_keys
        ].isna().any(
            axis=1
        ).sum()
    )

    duplicate_business_keys = int(
        data.duplicated(
            subset=business_keys,
            keep=False
        ).sum()
    )

    if null_business_keys:
        raise RuntimeError(
            f"{null_business_keys} rows have null "
            "business-key values."
        )

    if duplicate_business_keys:
        raise RuntimeError(
            f"{duplicate_business_keys} rows participate "
            "in duplicate business keys."
        )

    return {
        "Rows":
            int(
                len(
                    data
                )
            ),

        "UniqueIndicators":
            int(
                data[
                    "IndicatorID"
                ].nunique(
                    dropna=True
                )
            ),

        "NullBusinessKeyRows":
            null_business_keys,

        "DuplicateBusinessKeyRows":
            duplicate_business_keys
    }


def prepare_numeric_data(
    data: pd.DataFrame,
    dataset_types: Tuple[str, ...]
) -> pd.DataFrame:
    """
    Convert required model columns to numeric safely.
    """

    prepared_data = data.copy()

    numeric_columns = [
        "Year",
        "Quarter",
        "PeriodIndex",
        "QuarterNumber",
        "YearNumber"
    ]

    for dataset_type in dataset_types:

        configuration = TRACK_CONFIGURATIONS[
            dataset_type
        ]

        numeric_columns.extend(
            configuration[
                "Features"
            ]
        )

        numeric_columns.append(
            configuration[
                "TargetColumn"
            ]
        )

    numeric_columns = list(
        dict.fromkeys(
            numeric_columns
        )
    )

    for column in numeric_columns:

        prepared_data[
            column
        ] = pd.to_numeric(
            prepared_data[
                column
            ],
            errors="coerce"
        )

    prepared_data = prepared_data.replace(
        [
            np.inf,
            -np.inf
        ],
        np.nan
    )

    return prepared_data


# ============================================================
# TRACK PREPARATION
# ============================================================

def prepare_track_data(
    data: pd.DataFrame,
    dataset_type: str,
    training_share: float = DEFAULT_TRAINING_SHARE
) -> Dict[str, Any]:
    """
    Prepare one model track and reproduce the validated
    chronological 80/20 split within each indicator.
    """

    if dataset_type not in TRACK_CONFIGURATIONS:
        raise ValueError(
            "Unsupported dataset type: "
            f"{dataset_type}"
        )

    if not (
        0.0
        < float(
            training_share
        )
        < 1.0
    ):
        raise ValueError(
            "training_share must be between 0 and 1."
        )

    configuration = TRACK_CONFIGURATIONS[
        dataset_type
    ]

    features = list(
        configuration[
            "Features"
        ]
    )

    target_column = configuration[
        "TargetColumn"
    ]

    required_columns = list(
        dict.fromkeys(
            [
                "IndicatorID",
                "PeriodIndex"
            ]
            + features
            + [
                target_column
            ]
        )
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        raise KeyError(
            f"{dataset_type} track is missing columns: "
            + ", ".join(
                missing_columns
            )
        )

    modeling_data = data.dropna(
        subset=required_columns
    ).copy()

    modeling_data = modeling_data.replace(
        [
            np.inf,
            -np.inf
        ],
        np.nan
    )

    modeling_data = modeling_data.dropna(
        subset=required_columns
    ).copy()

    modeling_data = (
        modeling_data
        .sort_values(
            [
                "IndicatorID",
                "PeriodIndex"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    modeling_data[
        "SequenceNumber"
    ] = (
        modeling_data
        .groupby(
            "IndicatorID"
        )
        .cumcount()
    )

    modeling_data[
        "SequenceTotal"
    ] = (
        modeling_data
        .groupby(
            "IndicatorID"
        )[
            "IndicatorID"
        ]
        .transform(
            "size"
        )
    )

    modeling_data[
        "RelativePosition"
    ] = (
        modeling_data[
            "SequenceNumber"
        ]
        + 1
    ) / modeling_data[
        "SequenceTotal"
    ]

    training_data = modeling_data[
        modeling_data[
            "RelativePosition"
        ].le(
            float(
                training_share
            )
        )
    ].copy()

    testing_data = modeling_data[
        modeling_data[
            "RelativePosition"
        ].gt(
            float(
                training_share
            )
        )
    ].copy()

    if modeling_data.empty:
        raise RuntimeError(
            f"{dataset_type} modeling dataset is empty."
        )

    if training_data.empty:
        raise RuntimeError(
            f"{dataset_type} training dataset is empty."
        )

    if testing_data.empty:
        raise RuntimeError(
            f"{dataset_type} testing dataset is empty."
        )

    return {
        "DatasetType":
            dataset_type,

        "Configuration":
            configuration,

        "Features":
            features,

        "TargetColumn":
            target_column,

        "ModelingData":
            modeling_data,

        "TrainingData":
            training_data,

        "TestingData":
            testing_data,

        "Audit": {
            "DatasetType":
                dataset_type,

            "AnalysisTrack":
                configuration[
                    "AnalysisTrack"
                ],

            "TargetColumn":
                target_column,

            "Features":
                features,

            "ModelingRows":
                int(
                    len(
                        modeling_data
                    )
                ),

            "TrainingRows":
                int(
                    len(
                        training_data
                    )
                ),

            "TestingRows":
                int(
                    len(
                        testing_data
                    )
                ),

            "ModelingIndicators":
                int(
                    modeling_data[
                        "IndicatorID"
                    ].nunique()
                ),

            "TrainingIndicators":
                int(
                    training_data[
                        "IndicatorID"
                    ].nunique()
                ),

            "TestingIndicators":
                int(
                    testing_data[
                        "IndicatorID"
                    ].nunique()
                )
        }
    }


# ============================================================
# MODEL TRAINING AND EVALUATION
# ============================================================

def calculate_metrics(
    actual: pd.Series | np.ndarray,
    prediction: pd.Series | np.ndarray
) -> Tuple[float, float]:
    """
    Calculate MAE and RMSE.
    """

    actual_values = np.asarray(
        actual,
        dtype=float
    )

    prediction_values = np.asarray(
        prediction,
        dtype=float
    )

    if len(
        actual_values
    ) != len(
        prediction_values
    ):
        raise ValueError(
            "Actual and prediction arrays have "
            "different lengths."
        )

    if len(
        actual_values
    ) == 0:
        raise ValueError(
            "Metric calculation received no observations."
        )

    mae = mean_absolute_error(
        actual_values,
        prediction_values
    )

    rmse = math.sqrt(
        mean_squared_error(
            actual_values,
            prediction_values
        )
    )

    return (
        float(
            mae
        ),
        float(
            rmse
        )
    )


def create_candidate_models(
    random_state: int = DEFAULT_RANDOM_STATE
) -> Dict[str, Any]:
    """
    Create the validated candidate model configurations.
    """

    return {
        "Linear Regression":
            LinearRegression(),

        "Random Forest":
            RandomForestRegressor(
                n_estimators=300,
                max_depth=8,
                min_samples_leaf=5,
                random_state=random_state,
                n_jobs=-1
            ),

        "XGBoost":
            XGBRegressor(
                n_estimators=300,
                max_depth=3,
                learning_rate=0.03,
                subsample=0.80,
                colsample_bytree=0.80,
                objective="reg:squarederror",
                random_state=random_state,
                n_jobs=-1,
                verbosity=0
            )
    }


def train_candidate_models(
    prepared_track: Dict[str, Any],
    random_state: int = DEFAULT_RANDOM_STATE
) -> Dict[str, Any]:
    """
    Train and evaluate all approved candidate models for
    one dataset track.
    """

    dataset_type = prepared_track[
        "DatasetType"
    ]

    configuration = prepared_track[
        "Configuration"
    ]

    features = prepared_track[
        "Features"
    ]

    target_column = prepared_track[
        "TargetColumn"
    ]

    training_data = prepared_track[
        "TrainingData"
    ]

    testing_data = prepared_track[
        "TestingData"
    ]

    current_column = configuration[
        "CurrentColumn"
    ]

    X_train = training_data[
        features
    ].copy()

    y_train = training_data[
        target_column
    ].copy()

    X_test = testing_data[
        features
    ].copy()

    y_test = testing_data[
        target_column
    ].copy()

    result_rows = []

    trained_models = {}

    prediction_columns = [
        column
        for column in [
            "IndicatorID",
            "Project",
            "IndicatorName",
            "Year",
            "Quarter",
            "PeriodIndex",
            "PeriodLabel",
            current_column,
            target_column
        ]
        if column in testing_data.columns
    ]

    predictions = testing_data[
        prediction_columns
    ].copy()

    predictions[
        "DatasetType"
    ] = dataset_type

    predictions[
        "AnalysisTrack"
    ] = configuration[
        "AnalysisTrack"
    ]

    predictions[
        "TargetScale"
    ] = configuration[
        "TargetScale"
    ]

    # --------------------------------------------------------
    # Naive Persistence
    # --------------------------------------------------------

    naive_prediction = (
        testing_data[
            current_column
        ]
        .to_numpy(
            dtype=float
        )
    )

    naive_mae, naive_rmse = calculate_metrics(
        y_test,
        naive_prediction
    )

    predictions[
        "NaivePersistencePrediction"
    ] = naive_prediction

    result_rows.append(
        {
            "AnalysisTrack":
                configuration[
                    "AnalysisTrack"
                ],

            "Model":
                "Naive Persistence",

            "TargetScale":
                configuration[
                    "TargetScale"
                ],

            "TestRows":
                int(
                    len(
                        testing_data
                    )
                ),

            "MAE":
                naive_mae,

            "RMSE":
                naive_rmse,

            "DatasetType":
                dataset_type
        }
    )

    # --------------------------------------------------------
    # Machine-learning models
    # --------------------------------------------------------

    candidate_models = create_candidate_models(
        random_state=random_state
    )

    for model_name, model in candidate_models.items():

        model.fit(
            X_train,
            y_train
        )

        prediction = model.predict(
            X_test
        )

        mae, rmse = calculate_metrics(
            y_test,
            prediction
        )

        prediction_column = (
            model_name
            .replace(
                " ",
                ""
            )
            + "Prediction"
        )

        predictions[
            prediction_column
        ] = prediction

        result_rows.append(
            {
                "AnalysisTrack":
                    configuration[
                        "AnalysisTrack"
                    ],

                "Model":
                    model_name,

                "TargetScale":
                    configuration[
                        "TargetScale"
                    ],

                "TestRows":
                    int(
                        len(
                            testing_data
                        )
                    ),

                "MAE":
                    mae,

                "RMSE":
                    rmse,

                "DatasetType":
                    dataset_type
            }
        )

        trained_models[
            model_name
        ] = model

    raw_results = pd.DataFrame(
        result_rows
    )

    return {
        "DatasetType":
            dataset_type,

        "RawResults":
            raw_results,

        "Predictions":
            predictions,

        "TrainedModels":
            trained_models,

        "PreparedTrack":
            prepared_track
    }


# ============================================================
# GOVERNANCE RANKING
# ============================================================

def evaluate_models(
    raw_results: pd.DataFrame,
    evaluation_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Rank models using the approved governance rule:

    1. Lowest RMSE
    2. Lowest MAE as the secondary ordering rule
    """

    required_columns = [
        "AnalysisTrack",
        "Model",
        "TargetScale",
        "TestRows",
        "MAE",
        "RMSE",
        "DatasetType"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in raw_results.columns
    ]

    if missing_columns:
        raise KeyError(
            "Raw result columns are missing: "
            + ", ".join(
                missing_columns
            )
        )

    evaluated_results = raw_results.copy()

    evaluated_results[
        "MAE_Rank"
    ] = (
        evaluated_results
        .groupby(
            "DatasetType"
        )[
            "MAE"
        ]
        .rank(
            method="min",
            ascending=True
        )
        .astype(
            int
        )
    )

    evaluated_results[
        "RMSE_Rank"
    ] = (
        evaluated_results
        .groupby(
            "DatasetType"
        )[
            "RMSE"
        ]
        .rank(
            method="min",
            ascending=True
        )
        .astype(
            int
        )
    )

    evaluated_results = (
        evaluated_results
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

    evaluated_results[
        "GovernanceRank"
    ] = (
        evaluated_results
        .groupby(
            "DatasetType"
        )
        .cumcount()
        + 1
    )

    evaluated_results[
        "IsRecommended"
    ] = (
        evaluated_results[
            "GovernanceRank"
        ].eq(
            1
        )
        .astype(
            int
        )
    )

    evaluated_results[
        "SelectionRule"
    ] = (
        "Lowest RMSE, then lowest MAE"
    )

    if evaluation_date is None:

        evaluation_date = datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d"
        )

    evaluated_results[
        "EvaluationDate"
    ] = evaluation_date

    output_columns = [
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

    return evaluated_results[
        output_columns
    ].copy()


def generate_recommendations(
    evaluated_results: pd.DataFrame
) -> pd.DataFrame:
    """
    Return exactly one recommended model per dataset track.
    """

    recommendations = (
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

    expected_tracks = set(
        evaluated_results[
            "DatasetType"
        ].dropna().astype(
            str
        )
    )

    recommendation_tracks = set(
        recommendations[
            "DatasetType"
        ].dropna().astype(
            str
        )
    )

    if recommendation_tracks != expected_tracks:
        raise RuntimeError(
            "The recommendation output does not contain "
            "exactly one recommendation for every "
            "evaluated dataset track."
        )

    duplicate_recommendations = (
        recommendations
        .groupby(
            "DatasetType"
        )
        .size()
    )

    if not duplicate_recommendations.eq(
        1
    ).all():
        raise RuntimeError(
            "More than one recommendation was produced "
            "for a dataset track."
        )

    return recommendations


# ============================================================
# COMPLETE READ-ONLY PIPELINE
# ============================================================

def run_retraining_pipeline(
    database_file: str | Path,
    dataset_types: Tuple[str, ...] = SUPPORTED_DATASET_TYPES,
    training_share: float = DEFAULT_TRAINING_SHARE,
    random_state: int = DEFAULT_RANDOM_STATE,
    evaluation_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the complete reusable read-only retraining pipeline.

    No database table is modified.
    No candidate is registered.
    No model is promoted.
    """

    run_started_utc = datetime.now(
        timezone.utc
    )

    dataset_types = tuple(
        dataset_types
    )

    invalid_dataset_types = [
        dataset_type
        for dataset_type in dataset_types
        if dataset_type not in SUPPORTED_DATASET_TYPES
    ]

    if invalid_dataset_types:
        raise ValueError(
            "Unsupported dataset types: "
            + ", ".join(
                invalid_dataset_types
            )
        )

    database_validation = validate_database(
        database_file
    )

    dashboard_data = load_dashboard_data(
        database_file
    )

    source_validation = validate_source_data(
        dashboard_data,
        dataset_types
    )

    prepared_data = prepare_numeric_data(
        dashboard_data,
        dataset_types
    )

    track_outputs = {}

    all_raw_results = []

    all_predictions = []

    track_audits = []

    trained_models = {}

    for dataset_type in dataset_types:

        prepared_track = prepare_track_data(
            data=prepared_data,
            dataset_type=dataset_type,
            training_share=training_share
        )

        trained_track = train_candidate_models(
            prepared_track=prepared_track,
            random_state=random_state
        )

        track_outputs[
            dataset_type
        ] = trained_track

        all_raw_results.append(
            trained_track[
                "RawResults"
            ]
        )

        all_predictions.append(
            trained_track[
                "Predictions"
            ]
        )

        track_audits.append(
            prepared_track[
                "Audit"
            ]
        )

        trained_models[
            dataset_type
        ] = trained_track[
            "TrainedModels"
        ]

    combined_raw_results = pd.concat(
        all_raw_results,
        ignore_index=True
    )

    evaluated_results = evaluate_models(
        raw_results=combined_raw_results,
        evaluation_date=evaluation_date
    )

    recommendations = generate_recommendations(
        evaluated_results
    )

    combined_predictions = pd.concat(
        all_predictions,
        ignore_index=True
    )

    track_audit = pd.DataFrame(
        track_audits
    )

    run_finished_utc = datetime.now(
        timezone.utc
    )

    result = {
        "Status":
            "Completed",

        "ReadOnly":
            True,

        "DatabaseValidation":
            database_validation,

        "SourceValidation":
            source_validation,

        "RunStartedUTC":
            run_started_utc.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "RunFinishedUTC":
            run_finished_utc.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "DatasetTypes":
            list(
                dataset_types
            ),

        "TrackAudit":
            track_audit,

        "Performance":
            evaluated_results,

        "Recommendations":
            recommendations,

        "Predictions":
            combined_predictions,

        "TrainedModels":
            trained_models,

        "TrackOutputs":
            track_outputs,

        "DatabaseWritesPerformed":
            False,

        "AutomaticPromotionPerformed":
            False
    }

    return result


__all__ = [
    "TRACK_CONFIGURATIONS",
    "SUPPORTED_DATASET_TYPES",
    "MODEL_NAMES",
    "validate_database",
    "load_dashboard_data",
    "validate_source_data",
    "prepare_numeric_data",
    "prepare_track_data",
    "calculate_metrics",
    "create_candidate_models",
    "train_candidate_models",
    "evaluate_models",
    "generate_recommendations",
    "run_retraining_pipeline"
]

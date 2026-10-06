import math
from datetime import datetime, timezone

import pandas as pd


PREDICTION_COLUMN_MAP = {
    "Naive Persistence":
        "NaivePersistencePrediction",

    "Linear Regression":
        "LinearRegressionPrediction",

    "Random Forest":
        "RandomForestPrediction",

    "XGBoost":
        "XGBoostPrediction",
}


def build_forecast_verification_staging(
    predictions_df: pd.DataFrame,
    recommendations_df: pd.DataFrame,
    upload_batch_id: str,
    evaluation_timestamp_utc: str | None = None
) -> dict[str, pd.DataFrame]:
    """
    Build forecast-verification staging datasets from the
    latest retraining predictions.

    Only the recommended Original-track model is included,
    matching the historical forecast-verification methodology.

    This function performs no database writes.
    """

    if predictions_df.empty:
        raise ValueError(
            "The retraining prediction output is empty."
        )

    if recommendations_df.empty:
        raise ValueError(
            "The retraining recommendation output is empty."
        )

    if not evaluation_timestamp_utc:
        evaluation_timestamp_utc = datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    original_recommendation = recommendations_df[
        recommendations_df[
            "DatasetType"
        ]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("original")
    ].copy()

    if original_recommendation.empty:
        raise ValueError(
            "No recommended Original-track model was found."
        )

    recommendation = original_recommendation.iloc[0]

    recommended_model = str(
        recommendation[
            "Model"
        ]
    ).strip()

    prediction_column = PREDICTION_COLUMN_MAP.get(
        recommended_model
    )

    if prediction_column is None:
        raise ValueError(
            "No prediction-column mapping exists for "
            f"the recommended model '{recommended_model}'."
        )

    original_predictions = predictions_df[
        predictions_df[
            "DatasetType"
        ]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("original")
    ].copy()

    if original_predictions.empty:
        raise ValueError(
            "No Original-track prediction rows were produced."
        )

    required_columns = [
        "IndicatorID",
        "Project",
        "Year",
        "Quarter",
        "PeriodIndex",
        "PeriodLabel",
        "A_CurrentAR",
        "A_NextQuarterAR",
        prediction_column,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in original_predictions.columns
    ]

    if missing_columns:
        raise ValueError(
            "Prediction output is missing required columns: "
            + ", ".join(
                missing_columns
            )
        )

    archive = pd.DataFrame()

    archive[
        "ProjectID"
    ] = (
        original_predictions[
            "Project"
        ]
        .astype(str)
        .str.strip()
    )

    archive[
        "IndicatorID"
    ] = (
        original_predictions[
            "IndicatorID"
        ]
        .astype(str)
        .str.strip()
    )

    if "IndicatorName" in original_predictions.columns:

        archive[
            "IndicatorName"
        ] = (
            original_predictions[
                "IndicatorName"
            ]
        )

    else:

        archive[
            "IndicatorName"
        ] = pd.NA
    archive[
        "Year"
    ] = pd.to_numeric(
        original_predictions[
            "Year"
        ],
        errors="coerce"
    )

    archive[
        "Quarter"
    ] = pd.to_numeric(
        original_predictions[
            "Quarter"
        ],
        errors="coerce"
    )

    archive[
        "PeriodIndex"
    ] = pd.to_numeric(
        original_predictions[
            "PeriodIndex"
        ],
        errors="coerce"
    )

    archive[
        "PeriodLabel"
    ] = (
        original_predictions[
            "PeriodLabel"
        ]
        .astype(str)
        .str.strip()
    )

    archive[
        "CurrentActualValue"
    ] = pd.to_numeric(
        original_predictions[
            "A_CurrentAR"
        ],
        errors="coerce"
    )

    archive[
        "ActualValue"
    ] = pd.to_numeric(
        original_predictions[
            "A_NextQuarterAR"
        ],
        errors="coerce"
    )

    archive[
        "PredictedValue"
    ] = pd.to_numeric(
        original_predictions[
            prediction_column
        ],
        errors="coerce"
    )

    archive = (
        archive
        .dropna(
            subset=[
                "ActualValue",
                "PredictedValue"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    if archive.empty:

        raise ValueError(
            "No valid forecast-verification records "
            "remained after numeric validation."
        )

    archive[
        "SignedError"
    ] = (
        archive[
            "ActualValue"
        ]
        -
        archive[
            "PredictedValue"
        ]
    )

    archive[
        "AbsoluteError"
    ] = (
        archive[
            "SignedError"
        ].abs()
    )

    archive[
        "SquaredError"
    ] = (
        archive[
            "SignedError"
        ]
        ** 2
    )

    archive[
        "ForecastStatus"
    ] = "Verified"

    archive[
        "DatasetType"
    ] = "Original"

    archive[
        "Model"
    ] = recommended_model

    archive[
        "Version"
    ] = str(
        recommendation.get(
            "Version",
            evaluation_timestamp_utc
        )
    )

    archive[
        "EvaluationType"
    ] = "Lifecycle Holdout Evaluation"

    archive[
        "ForecastCreatedUTC"
    ] = evaluation_timestamp_utc

    archive[
        "EvaluationTimestampUTC"
    ] = evaluation_timestamp_utc

    archive[
        "UploadBatchID"
    ] = str(
        upload_batch_id
    )

    archive[
        "ForecastOriginPeriod"
    ] = archive[
        "PeriodLabel"
    ]

    archive[
        "ForecastTargetPeriod"
    ] = archive[
        "PeriodLabel"
    ]

    archive[
        "ForecastOriginIndex"
    ] = archive[
        "PeriodIndex"
    ]

    archive[
        "ForecastTargetIndex"
    ] = archive[
        "PeriodIndex"
    ]

    archive[
        "ArchiveKey"
    ] = (
        archive[
            "UploadBatchID"
        ].astype(str)
        + "|"
        + archive[
            "DatasetType"
        ].astype(str)
        + "|"
        + archive[
            "Model"
        ].astype(str)
        + "|"
        + archive[
            "IndicatorID"
        ].astype(str)
        + "|"
        + archive[
            "PeriodLabel"
        ].astype(str)
        + "|"
        + archive.index.astype(str)
    )

    archive_columns = [
        "ArchiveKey",
        "Version",
        "Model",
        "DatasetType",
        "EvaluationType",
        "ProjectID",
        "IndicatorID",
        "IndicatorName",
        "Year",
        "Quarter",
        "PeriodIndex",
        "PeriodLabel",
        "ForecastOriginPeriod",
        "ForecastTargetPeriod",
        "ForecastOriginIndex",
        "ForecastTargetIndex",
        "ForecastCreatedUTC",
        "EvaluationTimestampUTC",
        "UploadBatchID",
        "CurrentActualValue",
        "PredictedValue",
        "ActualValue",
        "SignedError",
        "AbsoluteError",
        "SquaredError",
        "ForecastStatus",
    ]

    archive = archive[
        archive_columns
    ].copy()

    absolute_error = archive[
        "AbsoluteError"
    ]

    squared_error = archive[
        "SquaredError"
    ]

    verification_metrics = pd.DataFrame(
        [
            {
                "EvaluationTimestampUTC":
                    evaluation_timestamp_utc,

                "UploadBatchID":
                    str(
                        upload_batch_id
                    ),

                "EvaluationType":
                    "Lifecycle Holdout Evaluation",

                "DatasetType":
                    "Original",

                "Model":
                    recommended_model,

                "Version":
                    archive[
                        "Version"
                    ].iloc[0],

                "VerifiedForecasts":
                    int(
                        len(
                            archive
                        )
                    ),

                "PendingForecasts":
                    0,

                "MeanAbsoluteError":
                    float(
                        absolute_error.mean()
                    ),

                "MedianAbsoluteError":
                    float(
                        absolute_error.median()
                    ),

                "RootMeanSquaredError":
                    float(
                        math.sqrt(
                            squared_error.mean()
                        )
                    ),

                "P90AbsoluteError":
                    float(
                        absolute_error.quantile(
                            0.90
                        )
                    ),

                "P95AbsoluteError":
                    float(
                        absolute_error.quantile(
                            0.95
                        )
                    ),

                "MaximumAbsoluteError":
                    float(
                        absolute_error.max()
                    ),

                "ZeroErrorForecasts":
                    int(
                        absolute_error.eq(
                            0
                        ).sum()
                    ),

                "SourceFile":
                    "Lifecycle Retraining Pipeline",
            }
        ]
    )

    project_rows = []

    for project_id, project_group in archive.groupby(
        "ProjectID",
        dropna=False
    ):

        project_absolute_error = project_group[
            "AbsoluteError"
        ]

        project_squared_error = project_group[
            "SquaredError"
        ]

        project_rows.append(
            {
                "ProjectID":
                    str(
                        project_id
                    ),

                "VerifiedForecasts":
                    int(
                        len(
                            project_group
                        )
                    ),

                "MeanAbsoluteError":
                    float(
                        project_absolute_error.mean()
                    ),

                "MedianAbsoluteError":
                    float(
                        project_absolute_error.median()
                    ),

                "MaximumAbsoluteError":
                    float(
                        project_absolute_error.max()
                    ),

                "RootMeanSquaredError":
                    float(
                        math.sqrt(
                            project_squared_error.mean()
                        )
                    ),

                "DatasetType":
                    "Original",

                "Model":
                    recommended_model,

                "Version":
                    archive[
                        "Version"
                    ].iloc[0],

                "EvaluationType":
                    "Lifecycle Holdout Evaluation",

                "EvaluationTimestampUTC":
                    evaluation_timestamp_utc,

                "UploadBatchID":
                    str(
                        upload_batch_id
                    ),
            }
        )

    project_metrics = pd.DataFrame(
        project_rows
    )

    return {
        "PredictionArchive":
            archive,

        "VerificationMetrics":
            verification_metrics,

        "ProjectMetrics":
            project_metrics,
    }
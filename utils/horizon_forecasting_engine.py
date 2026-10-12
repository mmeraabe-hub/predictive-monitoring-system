import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error


FEATURE_COLUMNS = [
    "AchievementRatio",
    "AnnualProgress",
    "AnnualTimeProgress",
    "LoPProgress",
    "LoPTimeProgress",
    "Year",
    "Quarter",
    "PeriodIndex",
]


def prepare_numeric_data(data):

    prepared_data = data.copy()

    for column in FEATURE_COLUMNS:

        if column not in prepared_data.columns:

            prepared_data[column] = np.nan

        prepared_data[column] = pd.to_numeric(
            prepared_data[column],
            errors="coerce"
        )

    return prepared_data


def create_candidate_models():

    return {
        "Linear Regression":
            LinearRegression(),

        "Random Forest":
            RandomForestRegressor(
                n_estimators=200,
                min_samples_leaf=3,
                random_state=42
            ),
    }


def build_annual_training_data(
    monitoring_data
):

    data = prepare_numeric_data(
        monitoring_data
    )

    required_columns = [
        "Project",
        "IndicatorID",
        "Year",
        "PeriodIndex",
        "AnnualProgress",
        "AnnualTimeProgress",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:

        raise ValueError(
            "Annual training data is missing columns: "
            + ", ".join(
                missing_columns
            )
        )

    annual_outcomes = (
        data
        .dropna(
            subset=[
                "Project",
                "IndicatorID",
                "Year",
                "PeriodIndex",
                "AnnualProgress"
            ]
        )
        .sort_values(
            "PeriodIndex"
        )
        .groupby(
            [
                "Project",
                "IndicatorID",
                "Year"
            ],
            as_index=False
        )
        .tail(1)
        [
            [
                "Project",
                "IndicatorID",
                "Year",
                "AnnualProgress"
            ]
        ]
        .rename(
            columns={
                "AnnualProgress":
                    "AnnualOutcomeRatio"
            }
        )
    )

    training_data = data.merge(
        annual_outcomes,
        on=[
            "Project",
            "IndicatorID",
            "Year"
        ],
        how="inner"
    )

    training_data = training_data.dropna(
        subset=(
            FEATURE_COLUMNS
            +
            [
                "AnnualOutcomeRatio"
            ]
        )
    )

    return training_data

    training_data = training_data.dropna(
        subset=(
            FEATURE_COLUMNS
            +
            [
                "LoPOutcomeRatio"
            ]
        )
    )

    training_data[
        "LoPOutcomeRatio"
    ] = pd.to_numeric(
        training_data[
            "LoPOutcomeRatio"
        ],
        errors="coerce"
    )

    training_data[
        "LoPProgress"
    ] = pd.to_numeric(
        training_data[
            "LoPProgress"
        ],
        errors="coerce"
    )

    training_data = training_data[
        training_data[
            "LoPOutcomeRatio"
        ].between(
            0.0,
            3.0,
            inclusive="both"
        )
        &
        training_data[
            "LoPProgress"
        ].between(
            0.0,
            3.0,
            inclusive="both"
        )
    ].copy()

    return training_data


def build_lop_training_data(
    monitoring_data
):

    data = prepare_numeric_data(
        monitoring_data
    )

    required_columns = [
        "Project",
        "IndicatorID",
        "PeriodIndex",
        "LoPProgress",
        "LoPTimeProgress",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:

        raise ValueError(
            "LoP training data is missing columns: "
            + ", ".join(
                missing_columns
            )
        )

    completed_records = data[
        data[
            "LoPTimeProgress"
        ].ge(0.999)
    ].copy()

    completed_records[
        "LoPProgress"
    ] = pd.to_numeric(
        completed_records[
            "LoPProgress"
        ],
        errors="coerce"
    )

    completed_records = completed_records[
        completed_records[
            "LoPProgress"
        ].between(
            0.0,
            3.0,
            inclusive="both"
        )
    ].copy()

    completed_outcomes = (
        completed_records
        .dropna(
            subset=[
                "Project",
                "IndicatorID",
                "PeriodIndex",
                "LoPProgress"
            ]
        )
        .sort_values(
            "PeriodIndex"
        )
        .groupby(
            [
                "Project",
                "IndicatorID"
            ],
            as_index=False
        )
        .tail(1)
        [
            [
                "Project",
                "IndicatorID",
                "LoPProgress"
            ]
        ]
        .rename(
            columns={
                "LoPProgress":
                    "LoPOutcomeRatio"
            }
        )
    )

    if completed_outcomes.empty:

        return pd.DataFrame()

    training_data = data.merge(
        completed_outcomes,
        on=[
            "Project",
            "IndicatorID"
        ],
        how="inner"
    )

    training_data = training_data[
        training_data[
            "LoPTimeProgress"
        ].lt(1.0)
    ].copy()

    training_data = training_data.dropna(
        subset=(
            FEATURE_COLUMNS
            +
            [
                "LoPOutcomeRatio"
            ]
        )
    )

    training_data[
        "LoPOutcomeRatio"
    ] = pd.to_numeric(
        training_data[
            "LoPOutcomeRatio"
        ],
        errors="coerce"
    )

    training_data[
        "LoPProgress"
    ] = pd.to_numeric(
        training_data[
            "LoPProgress"
        ],
        errors="coerce"
    )

    training_data = training_data[
        training_data[
            "LoPOutcomeRatio"
        ].between(
            0.0,
            3.0,
            inclusive="both"
        )
        &
        training_data[
            "LoPProgress"
        ].between(
            0.0,
            3.0,
            inclusive="both"
        )
    ].copy()

    return training_data


def evaluate_horizon_models(
    training_data,
    target_column,
    horizon_name
):

    if len(training_data) < 10:

        return (
            pd.DataFrame(),
            None,
            None
        )

    ordered_data = training_data.sort_values(
        "PeriodIndex"
    ).reset_index(
        drop=True
    )

    split_index = int(
        len(ordered_data) * 0.80
    )

    split_index = max(
        1,
        min(
            split_index,
            len(ordered_data) - 1
        )
    )

    train_data = ordered_data.iloc[
        :split_index
    ].copy()

    test_data = ordered_data.iloc[
        split_index:
    ].copy()

    if train_data.empty or test_data.empty:

        return (
            pd.DataFrame(),
            None,
            None
        )

    x_train = train_data[
        FEATURE_COLUMNS
    ]

    y_train = train_data[
        target_column
    ]

    x_test = test_data[
        FEATURE_COLUMNS
    ]

    y_test = test_data[
        target_column
    ]

    performance_rows = []

    for model_name, model in (
        create_candidate_models().items()
    ):

        model.fit(
            x_train,
            y_train
        )

        predictions = model.predict(
            x_test
        )

        

        mae = float(
            mean_absolute_error(
                y_test,
                predictions
            )
        )

        rmse = float(
            np.sqrt(
                mean_squared_error(
                    y_test,
                    predictions
                )
            )
        )

        performance_rows.append(
            {
                "ForecastHorizon":
                    horizon_name,

                "Model":
                    model_name,

                "TrainingRows":
                    int(
                        len(train_data)
                    ),

                "TestRows":
                    int(
                        len(test_data)
                    ),

                "MAE":
                    mae,

                "RMSE":
                    rmse,

                "SelectionRule":
                    "Lowest RMSE, then lowest MAE",
            }
        )

    performance = pd.DataFrame(
        performance_rows
    )

    performance = performance.sort_values(
        [
            "RMSE",
            "MAE"
        ]
    ).reset_index(
        drop=True
    )

    performance[
        "GovernanceRank"
    ] = (
        performance.index + 1
    )

    performance[
        "IsRecommended"
    ] = (
        performance[
            "GovernanceRank"
        ]
        .eq(1)
        .astype(int)
    )

    champion_name = str(
        performance.iloc[0][
            "Model"
        ]
    )

    champion_model = (
        create_candidate_models()[
            champion_name
        ]
    )

    champion_model.fit(
        ordered_data[
            FEATURE_COLUMNS
        ],
        ordered_data[
            target_column
        ]
    )

    return (
        performance,
        champion_model,
        champion_name
    )


def get_latest_indicator_snapshot(
    monitoring_data
):

    data = prepare_numeric_data(
        monitoring_data
    )

    required_columns = [
        "Project",
        "IndicatorID",
        "PeriodIndex",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:

        raise ValueError(
            "Latest snapshot is missing columns: "
            + ", ".join(
                missing_columns
            )
        )

    latest_snapshot = (
        data
        .dropna(
            subset=[
                "Project",
                "IndicatorID",
                "PeriodIndex"
            ]
        )
        .sort_values(
            "PeriodIndex"
        )
        .groupby(
            [
                "Project",
                "IndicatorID"
            ],
            as_index=False
        )
        .tail(1)
        .copy()
    )

    latest_snapshot = latest_snapshot.dropna(
        subset=FEATURE_COLUMNS
    )

    return latest_snapshot


def run_horizon_forecasting(
    database_file,
    upload_batch_id=""
):

    connection = sqlite3.connect(
        str(database_file)
    )

    try:

        monitoring_data = pd.read_sql_query(
            """
            SELECT *
            FROM dashboard_data
            """,
            connection
        )

    finally:

        connection.close()

    if monitoring_data.empty:

        raise RuntimeError(
            "dashboard_data is empty."
        )

    annual_training_data = (
        build_annual_training_data(
            monitoring_data
        )
    )

    lop_training_data = (
        build_lop_training_data(
            monitoring_data
        )
    )

    (
        annual_performance,
        annual_model,
        annual_champion
    ) = evaluate_horizon_models(
        training_data=annual_training_data,
        target_column="AnnualOutcomeRatio",
        horizon_name="Annual"
    )

    (
        lop_performance,
        lop_model,
        lop_champion
    ) = evaluate_horizon_models(
        training_data=lop_training_data,
        target_column="LoPOutcomeRatio",
        horizon_name="LoP"
    )

    performance_frames = [
        frame
        for frame in [
            annual_performance,
            lop_performance
        ]
        if not frame.empty
    ]

    if performance_frames:

        horizon_performance = pd.concat(
            performance_frames,
            ignore_index=True
        )

    else:

        horizon_performance = pd.DataFrame()

    latest_snapshot = get_latest_indicator_snapshot(
        monitoring_data
    )

    forecast_created_utc = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    forecast_rows = []

    horizon_definitions = [
        (
            "Annual",
            annual_model,
            annual_champion,
            annual_performance
        ),
        (
            "LoP",
            lop_model,
            lop_champion,
            lop_performance
        ),
    ]

    for (
        horizon_name,
        model,
        champion_name,
        performance
    ) in horizon_definitions:

        if (
            model is None
            or
            performance.empty
        ):

            continue

        prediction_snapshot = (
            latest_snapshot.copy()
        )

        if horizon_name == "LoP":

            prediction_snapshot[
                "LoPProgress"
            ] = pd.to_numeric(
                prediction_snapshot[
                    "LoPProgress"
                ],
                errors="coerce"
            )

            prediction_snapshot = (
                prediction_snapshot[
                    prediction_snapshot[
                        "LoPProgress"
                    ].between(
                        0.0,
                        3.0,
                        inclusive="both"
                    )
                ]
                .copy()
            )

        if prediction_snapshot.empty:

            continue

        predicted_values = model.predict(
            prediction_snapshot[
                FEATURE_COLUMNS
            ]
        )

        predicted_values = np.maximum(
            predicted_values,
            0.0
        )

        if horizon_name == "LoP":

            predicted_values = np.where(
                predicted_values <= 3.0,
                predicted_values,
                np.nan
            )

        

        champion_row = performance.iloc[0]

        for row_position, (
            row_index,
            snapshot_row
        ) in enumerate(
            prediction_snapshot.iterrows()
        ):

            forecast_ratio = float(
                predicted_values[
                    row_position
                ]
            )

            if pd.isna(
                forecast_ratio
            ):

                continue

            indicator_name = snapshot_row.get(
                "IndicatorName",
                snapshot_row[
                    "IndicatorID"
                ]
            )

            if pd.isna(
                indicator_name
            ):

                indicator_name = snapshot_row[
                    "IndicatorID"
                ]

            forecast_rows.append(
                {
                    "ForecastCreatedUTC":
                        forecast_created_utc,

                    "UploadBatchID":
                        str(
                            upload_batch_id
                        ),

                    "ForecastHorizon":
                        horizon_name,

                    "ForecastModel":
                        str(
                            champion_name
                        ),

                    "ProjectID":
                        str(
                            snapshot_row[
                                "Project"
                            ]
                        ),

                    "IndicatorID":
                        str(
                            snapshot_row[
                                "IndicatorID"
                            ]
                        ),

                    "IndicatorName":
                        str(
                            indicator_name
                        ),

                    "CurrentYear":
                        int(
                            snapshot_row[
                                "Year"
                            ]
                        ),

                    "CurrentQuarter":
                        int(
                            snapshot_row[
                                "Quarter"
                            ]
                        ),

                    "CurrentPeriodIndex":
                        int(
                            snapshot_row[
                                "PeriodIndex"
                            ]
                        ),

                    "CurrentAchievementRatio":
                        float(
                            snapshot_row[
                                "AchievementRatio"
                            ]
                        ),

                    "ForecastAchievementRatio":
                        forecast_ratio,

                    "ForecastGapToTarget":
                        float(
                            forecast_ratio - 1.0
                        ),

                    "ForecastStatus":
                        "Projected",

                    "EvaluationMAE":
                        float(
                            champion_row[
                                "MAE"
                            ]
                        ),

                    "EvaluationRMSE":
                        float(
                            champion_row[
                                "RMSE"
                            ]
                        ),

                    "ProjectionMethod":
                        (
                            "Separate machine-learning "
                            "horizon model"
                        ),
                }
            )

    horizon_forecasts = pd.DataFrame(
        forecast_rows
    )

    connection = sqlite3.connect(
        str(database_file)
    )

    try:

        connection.execute(
            "BEGIN IMMEDIATE"
        )

        horizon_performance.to_sql(
            "horizon_model_performance",
            connection,
            if_exists="replace",
            index=False
        )

        horizon_forecasts.to_sql(
            "horizon_forecast",
            connection,
            if_exists="replace",
            index=False
        )

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()

    return {
        "Performance":
            horizon_performance,

        "Forecasts":
            horizon_forecasts,

        "AnnualTrainingRows":
            int(
                len(
                    annual_training_data
                )
            ),

        "LoPTrainingRows":
            int(
                len(
                    lop_training_data
                )
            ),

        "AnnualChampion":
            annual_champion,

        "LoPChampion":
            lop_champion,
    }

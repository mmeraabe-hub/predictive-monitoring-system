import pandas as pd
import numpy as np
import sqlite3
import json
import uuid
def load_approved_batch(
    upload_batch_id,
    database_file="predictive_monitoring.db"
):

    conn = sqlite3.connect(
        database_file
    )

    try:

        batch = pd.read_sql_query(
            """
            SELECT *
            FROM itt_upload_batches
            WHERE UploadBatchID = ?
            """,
            conn,
            params=[upload_batch_id]
        )

        if batch.empty:
            raise ValueError(
                "Batch not found."
            )

        batch_row = batch.iloc[0]

        if (
            batch_row["UploadStatus"]
            != "Approved"
        ):
            raise ValueError(
                "Batch is not approved."
            )

        staged_rows = pd.read_sql_query(
            """
            SELECT *
            FROM uploaded_itt_staging
            WHERE UploadBatchID = ?
            ORDER BY RowNumber
            """,
            conn,
            params=[upload_batch_id]
        )

        return batch_row, staged_rows

    finally:
        conn.close()
def reconstruct_uploaded_itt(
    staged_rows
):

    records = []

    for _, row in staged_rows.iterrows():

        try:

            record = json.loads(
                row["RecordJSON"]
            )

            records.append(record)

        except Exception:
            continue

    return pd.DataFrame(records)
def transform_itt_to_longitudinal(
    itt_data
):
    """
    Convert wide ITT rows into
    Project Ã— Indicator Ã— Quarter rows.
    """

    records = []

    for _, row in itt_data.iterrows():

        indicator_id = row.get(
            "IndicatorID"
        )

        if (
            indicator_id is None
            or str(indicator_id).strip() == ""
        ):
            continue

        project = row.get(
            "Project"
        )

        indicator_name = row.get(
            "Indicators "
        )

        unit = row.get(
            "Unit of Measure"
        )

        lop_target = row.get(
            "Project Life Target"
        )

        baseline = row.get(
            "Baseline"
        )

        for year in range(1, 6):

            yearly_target_column = (
                f"Year {year} Target"
            )

            annual_target = row.get(
                yearly_target_column
            )

            for quarter in range(1, 5):

                target_col = (
                    f"Y{year}_Q{quarter}_Target"
                )

                actual_col = (
                    f"Y{year}_Q{quarter}_Actual"
                )

                if (
                    target_col not in row.index
                ):
                    continue

                quarter_target = row.get(
                    target_col
                )

                quarter_actual = row.get(
                    actual_col
                )

                if (
                    pd.isna(quarter_target)
                    and
                    pd.isna(quarter_actual)
                ):
                    continue

                period_index = (
                    ((year - 1) * 4)
                    + quarter
                )

                records.append(
                    {
                        "IndicatorID":
                            indicator_id,

                        "Project":
                            project,

                        "IndicatorName":
                            indicator_name,

                        "Unit":
                            unit,

                        "LoPTarget":
                            lop_target,

                        "Baseline":
                            baseline,

                        "Year":
                            year,

                        "Quarter":
                            quarter,

                        "PeriodIndex":
                            period_index,

                        "PeriodLabel":
                            (
                                f"Y{year}Q{quarter}"
                            ),

                        "QuarterTarget":
                            quarter_target,

                        "QuarterActual":
                            quarter_actual,

                        "AnnualTarget":
                            annual_target,
                    }
                )

    longitudinal = pd.DataFrame(
        records
    )

    return longitudinal
def build_dashboard_features(long_df, itt_df=None):

    import numpy as np
    import pandas as pd

    df = long_df.copy()

    # ==================================================
    # 1. VALIDATE REQUIRED BASE COLUMNS
    # ==================================================

    required_columns = [
        "IndicatorID",
        "Project",
        "IndicatorName",
        "Unit",
        "LoPTarget",
        "Baseline",
        "Year",
        "Quarter",
        "PeriodIndex",
        "PeriodLabel",
        "QuarterTarget",
        "QuarterActual",
        "AnnualTarget",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required longitudinal columns: "
            + ", ".join(missing_columns)
        )

    # ==================================================
    # 2. ENSURE NUMERIC DATA TYPES
    # ==================================================

    numeric_columns = [
        "LoPTarget",
        "Baseline",
        "Year",
        "Quarter",
        "PeriodIndex",
        "QuarterTarget",
        "QuarterActual",
        "AnnualTarget",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # ==================================================
    # 3. SORT CHRONOLOGICALLY
    # ==================================================

    df = df.sort_values(
        [
            "IndicatorID",
            "PeriodIndex",
        ]
    ).reset_index(drop=True)

    # ==================================================
    # 4. ACHIEVEMENT FEATURES
    # ==================================================

    df["AchievementRatio"] = np.where(
        (
            df["QuarterTarget"].notna()
            & (df["QuarterTarget"] != 0)
        ),
        (
            df["QuarterActual"]
            / df["QuarterTarget"]
        ),
        np.nan,
    )

    df["QuarterVariance"] = (
        df["QuarterActual"]
        - df["QuarterTarget"]
    )

    # ==================================================
    # 5. CUMULATIVE FEATURES
    # ==================================================

    df["CumulativeTarget"] = (
        df.groupby(
            "IndicatorID"
        )["QuarterTarget"]
        .transform(
            lambda values:
            values.fillna(0).cumsum()
        )
    )

    df["CumulativeActual"] = (
        df.groupby(
            "IndicatorID"
        )["QuarterActual"]
        .transform(
            lambda values:
            values.fillna(0).cumsum()
        )
    )

    # ==================================================
    # 6. LIFE-OF-PROJECT PROGRESS
    # ==================================================

    df["LoPProgress"] = np.nan

    lop_mask = (
        df["LoPTarget"].notna()
        & (df["LoPTarget"] != 0)
    )

    df.loc[
        lop_mask,
        "LoPProgress",
    ] = (
        df.loc[
            lop_mask,
            "CumulativeActual",
        ]
        / df.loc[
            lop_mask,
            "LoPTarget",
        ]
    )

    # ==================================================
    # 7. ACTUAL-VALUE LAG FEATURES
    # ==================================================

    indicator_groups = df.groupby(
        "IndicatorID"
    )

    df["Actual_Lag1"] = (
        indicator_groups["QuarterActual"]
        .shift(1)
    )

    df["Actual_Lag2"] = (
        indicator_groups["QuarterActual"]
        .shift(2)
    )

    df["Actual_Lag3"] = (
        indicator_groups["QuarterActual"]
        .shift(3)
    )

    df["AchievementRatio_Lag1"] = (
        indicator_groups["AchievementRatio"]
        .shift(1)
    )

    df["NextQuarterActual"] = (
        indicator_groups["QuarterActual"]
        .shift(-1)
    )

    # ==================================================
    # 8. ACHIEVEMENT-RATIO LAG FEATURES
    # ==================================================

    df["AR_Lag1"] = (
        indicator_groups["AchievementRatio"]
        .shift(1)
    )

    df["AR_Lag2"] = (
        indicator_groups["AchievementRatio"]
        .shift(2)
    )

    df["AR_Lag3"] = (
        indicator_groups["AchievementRatio"]
        .shift(3)
    )

    df["NextQuarterAR"] = (
        indicator_groups["AchievementRatio"]
        .shift(-1)
    )

    # ==================================================
    # 9. ORIGINAL AND CAPPED TRACKS
    # ==================================================

    df["AR_Original"] = pd.to_numeric(
        df["AchievementRatio"],
        errors="coerce",
    )

    df["AR_Capped"] = (
        df["AR_Original"]
        .clip(
            lower=0,
            upper=3,
        )
    )

    # Model A uses original achievement ratios.

    df["A_CurrentAR"] = (
        df["AR_Original"]
    )

    df["A_Lag1"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Original"]
        .shift(1)
    )

    df["A_Lag2"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Original"]
        .shift(2)
    )

    df["A_Lag3"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Original"]
        .shift(3)
    )

    df["A_NextQuarterAR"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Original"]
        .shift(-1)
    )

    # Model B uses achievement ratios capped at 3.

    df["B_CurrentAR"] = (
        df["AR_Capped"]
    )

    df["B_Lag1"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Capped"]
        .shift(1)
    )

    df["B_Lag2"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Capped"]
        .shift(2)
    )

    df["B_Lag3"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Capped"]
        .shift(3)
    )

    df["B_NextQuarterAR"] = (
        df.groupby(
            "IndicatorID"
        )["AR_Capped"]
        .shift(-1)
    )

    # ==================================================
    # 10. YEAR AND QUARTER NUMBERS
    # ==================================================

    df["QuarterNumber"] = (
        df["Quarter"]
    )

    df["YearNumber"] = (
        df["Year"]
    )

    # ==================================================
    # 11. BRING ANNUAL TARGET COLUMNS FROM ITT
    # ==================================================

    annual_target_columns = [
        "Year 1 Target",
        "Year 2 Target",
        "Year 3 Target",
        " Year 4 target",
        " Year 5 target",
    ]

    if itt_df is not None:

        available_target_columns = [
            column
            for column in annual_target_columns
            if column in itt_df.columns
        ]

        lookup_columns = [
            "IndicatorID"
        ] + available_target_columns

        annual_target_lookup = (
            itt_df[lookup_columns]
            .drop_duplicates(
                subset=["IndicatorID"],
                keep="last",
            )
            .copy()
        )

        for column in available_target_columns:
            annual_target_lookup[column] = (
                pd.to_numeric(
                    annual_target_lookup[column],
                    errors="coerce",
                )
            )

        columns_to_merge = [
            column
            for column in available_target_columns
            if column not in df.columns
        ]

        if columns_to_merge:
            df = df.merge(
                annual_target_lookup[
                    ["IndicatorID"]
                    + columns_to_merge
                ],
                on="IndicatorID",
                how="left",
                validate="many_to_one",
            )

    # Ensure all five target columns exist.

    for column in annual_target_columns:
        if column not in df.columns:
            df[column] = np.nan

    # ==================================================
    # 12. CURRENT ANNUAL PROGRESS
    # ==================================================

    df["CurrentYearActual"] = (
        df.groupby(
            [
                "IndicatorID",
                "Year",
            ]
        )["QuarterActual"]
        .cumsum()
    )

    df["AnnualProgress"] = np.where(
        (
            df["AnnualTarget"].notna()
            & (df["AnnualTarget"] != 0)
        ),
        (
            df["CurrentYearActual"]
            / df["AnnualTarget"]
        ),
        np.nan,
    )

    df["AnnualProgress"] = (
        df["AnnualProgress"]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
    )

    # ==================================================
    # 13. QUARTERS COMPLETED AND REMAINING
    # ==================================================

    df["QuartersCompletedInYear"] = (
        df.groupby(
            [
                "IndicatorID",
                "Year",
            ]
        )
        .cumcount()
        + 1
    )

    df["QuartersRemainingInYear"] = (
        4
        - df["QuartersCompletedInYear"]
    )

    # ==================================================
    # 14. ANNUAL TIME PROGRESS
    # ==================================================

    df["AnnualTimeProgress"] = (
        df["Quarter"]
        / 4
    )

    df["AnnualProgressGap"] = (
        df["AnnualProgress"]
        - df["AnnualTimeProgress"]
    )

    # ==================================================
    # 15. LIFE-OF-PROJECT TIME PROGRESS
    # ==================================================

    total_project_quarters = 20

    df["CurrentProjectQuarter"] = (
        (
            (df["Year"] - 1)
            * 4
        )
        + df["Quarter"]
    )

    df["LoPTimeProgress"] = (
        df["CurrentProjectQuarter"]
        / total_project_quarters
    )

    df["LoPProgressGap"] = (
        df["LoPProgress"]
        - df["LoPTimeProgress"]
    )

    # ==================================================
    # 16. FORECAST RATIOS
    # ==================================================

    df["AnnualForecastRatio"] = np.where(
        (
            df["AnnualTimeProgress"].notna()
            & (df["AnnualTimeProgress"] != 0)
        ),
        (
            df["AnnualProgress"]
            / df["AnnualTimeProgress"]
        ),
        np.nan,
    )

    df["LoPForecastRatio"] = np.where(
        (
            df["LoPTimeProgress"].notna()
            & (df["LoPTimeProgress"] != 0)
        ),
        (
            df["LoPProgress"]
            / df["LoPTimeProgress"]
        ),
        np.nan,
    )

    df["AnnualForecastRatio"] = (
        df["AnnualForecastRatio"]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
    )

    df["LoPForecastRatio"] = (
        df["LoPForecastRatio"]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
    )

    # ==================================================
    # 17. STATUS CLASSIFICATION
    # ==================================================

    def classify_quarter_status(row):

        target = row.get(
            "QuarterTarget"
        )

        actual = row.get(
            "QuarterActual"
        )

        ratio = row.get(
            "AchievementRatio"
        )

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

    df["QuarterStatus"] = (
        df.apply(
            classify_quarter_status,
            axis=1,
        )
    )

    df["AnnualStatus"] = (
        df["AnnualForecastRatio"]
        .apply(
            classify_forecast_status
        )
    )

    df["LoPStatus"] = (
        df["LoPForecastRatio"]
        .apply(
            classify_forecast_status
        )
    )

    # ==================================================
    # 18. FINAL DASHBOARD COLUMN ORDER
    # ==================================================

    dashboard_columns = [
        "IndicatorID",
        "Project",
        "IndicatorName",
        "Unit",
        "LoPTarget",
        "Baseline",
        "Year",
        "Quarter",
        "PeriodIndex",
        "PeriodLabel",
        "QuarterTarget",
        "QuarterActual",
        "AchievementRatio",
        "QuarterVariance",
        "CumulativeTarget",
        "CumulativeActual",
        "LoPProgress",
        "Actual_Lag1",
        "Actual_Lag2",
        "Actual_Lag3",
        "AchievementRatio_Lag1",
        "NextQuarterActual",
        "AR_Lag1",
        "AR_Lag2",
        "AR_Lag3",
        "NextQuarterAR",
        "AR_Original",
        "AR_Capped",
        "A_CurrentAR",
        "A_Lag1",
        "A_Lag2",
        "A_Lag3",
        "A_NextQuarterAR",
        "B_CurrentAR",
        "B_Lag1",
        "B_Lag2",
        "B_Lag3",
        "B_NextQuarterAR",
        "QuarterNumber",
        "YearNumber",
        "AnnualTarget",
        "Year 1 Target",
        "Year 2 Target",
        "Year 3 Target",
        " Year 4 target",
        " Year 5 target",
        "CurrentYearActual",
        "AnnualProgress",
        "QuartersCompletedInYear",
        "QuartersRemainingInYear",
        "AnnualTimeProgress",
        "AnnualProgressGap",
        "CurrentProjectQuarter",
        "LoPTimeProgress",
        "LoPProgressGap",
        "AnnualForecastRatio",
        "LoPForecastRatio",
        "QuarterStatus",
        "AnnualStatus",
        "LoPStatus",
    ]

    missing_final_columns = [
        column
        for column in dashboard_columns
        if column not in df.columns
    ]

    if missing_final_columns:
        raise ValueError(
            "Dashboard feature construction is incomplete. "
            "Missing columns: "
            + ", ".join(missing_final_columns)
        )

    df = df[
        dashboard_columns
    ].copy()

    return df

def get_candidate_dataset(
    dataset_type,
    candidate_model,
    candidate_version,
    db_path="predictive_monitoring.db"
):

    conn = sqlite3.connect(
        db_path
    )

    try:

        record = pd.read_sql_query(
            '''
            SELECT *
            FROM approved_dataset_registry
            WHERE DatasetType = ?
              AND CandidateModel = ?
              AND CandidateVersion = ?
            ORDER BY RegistryID DESC
            LIMIT 1
            ''',
            conn,
            params=[
                dataset_type,
                candidate_model,
                candidate_version
            ]
        )

    finally:

        conn.close()

    if record.empty:

        return None

    return record.iloc[0].to_dict()


def upsert_dashboard_data(
    dashboard_df,
    db_path="predictive_monitoring.db"
):

    if dashboard_df is None:
        raise ValueError(
            "dashboard_df cannot be None."
        )

    if dashboard_df.empty:
        raise ValueError(
            "dashboard_df contains no rows."
        )

    conn = sqlite3.connect(
        db_path
    )

    try:

        dashboard_df.to_sql(
            "dashboard_data",
            conn,
            if_exists="replace",
            index=False
        )

        conn.commit()

        return {
            "TotalRows":
                len(dashboard_df),

            "ProjectCount":
                dashboard_df[
                    "Project"
                ].nunique()
        }

    finally:

        conn.close()


def process_approved_batch(
    upload_batch_id,
    db_path="predictive_monitoring.db"
):
    """
    Load one approved upload batch, reconstruct its ITT,
    transform it into longitudinal form, build dashboard
    features, combine it with existing analytical data,
    remove duplicate records, and replace dashboard_data
    with the complete combined dataset.
    """

    import sqlite3
    import pandas as pd

    # --------------------------------------------------
    # 1. LOAD APPROVED STAGING RECORDS
    # --------------------------------------------------

    loaded_batch = load_approved_batch(
        upload_batch_id=upload_batch_id,
        database_file=db_path
    )

    if not isinstance(loaded_batch, tuple):
        raise TypeError(
            "load_approved_batch() must return a tuple."
        )

    if len(loaded_batch) != 2:
        raise ValueError(
            "load_approved_batch() returned an unexpected "
            f"tuple length: {len(loaded_batch)}"
        )

    batch_metadata = loaded_batch[0]
    staged_rows = loaded_batch[1]

    if not isinstance(staged_rows, pd.DataFrame):
        raise TypeError(
            "The second item returned by load_approved_batch() "
            "must be a pandas DataFrame, but received "
            f"{type(staged_rows).__name__}."
        )

    if staged_rows is None:
        raise ValueError(
            "No approved staging records were returned "
            f"for batch {upload_batch_id}."
        )

    if hasattr(staged_rows, "empty") and staged_rows.empty:
        raise ValueError(
            "The approved batch contains no staging records."
        )

    # --------------------------------------------------
    # 2. RECONSTRUCT THE ORIGINAL ITT
    # --------------------------------------------------

    itt_df = reconstruct_uploaded_itt(
        staged_rows
    )

    if itt_df is None or itt_df.empty:
        raise ValueError(
            "ITT reconstruction produced no records."
        )

    # --------------------------------------------------
    # 3. TRANSFORM TO LONGITUDINAL FORMAT
    # --------------------------------------------------

    long_df = transform_itt_to_longitudinal(
        itt_df
    )

    if long_df is None or long_df.empty:
        raise ValueError(
            "Longitudinal transformation produced no records."
        )

    # --------------------------------------------------
    # 4. BUILD DASHBOARD FEATURES FOR THE NEW BATCH
    # --------------------------------------------------

    new_dashboard_df = build_dashboard_features(
        long_df,
        itt_df=itt_df
    )

    if (
        new_dashboard_df is None
        or new_dashboard_df.empty
    ):
        raise ValueError(
            "Dashboard feature construction produced no records."
        )

    # --------------------------------------------------
    # 5. LOAD EXISTING DASHBOARD DATA
    # --------------------------------------------------

    conn = sqlite3.connect(
        db_path
    )

    try:
        table_exists = conn.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'dashboard_data'
            """
        ).fetchone()[0]

        if table_exists:
            existing_dashboard_df = pd.read_sql_query(
                """
                SELECT *
                FROM dashboard_data
                """,
                conn
            )
        else:
            existing_dashboard_df = pd.DataFrame()

    finally:
        conn.close()

    rows_before = len(
        existing_dashboard_df
    )

    projects_before = (
        existing_dashboard_df["Project"]
        .nunique()
        if (
            not existing_dashboard_df.empty
            and "Project" in existing_dashboard_df.columns
        )
        else 0
    )

    # --------------------------------------------------
    # 6. VALIDATE COLUMN COMPATIBILITY
    # --------------------------------------------------

    if not existing_dashboard_df.empty:

        existing_columns = set(
            existing_dashboard_df.columns
        )

        new_columns = set(
            new_dashboard_df.columns
        )

        missing_from_new = sorted(
            existing_columns - new_columns
        )

        extra_in_new = sorted(
            new_columns - existing_columns
        )

        if missing_from_new or extra_in_new:

            raise ValueError(
                "Existing and new dashboard schemas do not match.\n"
                f"Missing from new data: {missing_from_new}\n"
                f"Extra in new data: {extra_in_new}"
            )

        new_dashboard_df = new_dashboard_df[
            existing_dashboard_df.columns
        ].copy()

    # --------------------------------------------------
    # 7. COMBINE EXISTING AND NEW ANALYTICAL DATA
    # --------------------------------------------------

    if existing_dashboard_df.empty:

        combined_dashboard_df = (
            new_dashboard_df.copy()
        )

    else:

        combined_dashboard_df = pd.concat(
            [
                existing_dashboard_df,
                new_dashboard_df
            ],
            ignore_index=True
        )

    # One row per project, indicator, year and quarter.
    record_key = [
        "Project",
        "IndicatorID",
        "Year",
        "Quarter"
    ]

    missing_key_columns = [
        column
        for column in record_key
        if column not in combined_dashboard_df.columns
    ]

    if missing_key_columns:
        raise ValueError(
            "Required dashboard record keys are missing: "
            + ", ".join(missing_key_columns)
        )

    combined_dashboard_df = (
        combined_dashboard_df
        .sort_values(
            record_key
        )
        .drop_duplicates(
            subset=record_key,
            keep="last"
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------
    # 8. WRITE THE COMPLETE COMBINED DATASET
    # --------------------------------------------------

    upsert_result = upsert_dashboard_data(
        combined_dashboard_df,
        db_path=db_path
    )

    rows_after = len(
        combined_dashboard_df
    )

    projects_after = (
        combined_dashboard_df[
            "Project"
        ].nunique()
    )

    rows_added = (
        rows_after
        - rows_before
    )

    # --------------------------------------------------
    # 9. RETURN AUDITABLE ETL RESULTS
    # --------------------------------------------------

    return {
        "UploadBatchID":
            upload_batch_id,

        "SourceRows":
            len(staged_rows),

        "ReconstructedRows":
            len(itt_df),

        "LongitudinalRows":
            len(long_df),

        "NewDashboardRows":
            len(new_dashboard_df),

        "DashboardRowsBefore":
            rows_before,

        "DashboardRowsAfter":
            rows_after,

        "NetRowsAdded":
            rows_added,

        "ProjectsBefore":
            projects_before,

        "ProjectsAfter":
            projects_after,

        "DatabaseWriteResult":
            upsert_result
    }


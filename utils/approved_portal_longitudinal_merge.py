import sqlite3
from datetime import datetime

import pandas as pd


RAW_COLUMNS = [
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
    "Year 1 Target",
    "Year 2 Target",
    "Year 3 Target",
    " Year 4 target",
    " Year 5 target",
]


def _table_exists(connection, table_name):
    return connection.execute(
        """
        SELECT COUNT(1)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()[0] > 0


def _ensure_indicator_tracking_columns(connection):
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(itt_indicator_submission_staging)"
        ).fetchall()
    }

    additions = {
        "DatasetInclusionStatus": "TEXT",
        "DatasetIncludedAt": "TEXT",
        "DatasetIncludedBy": "TEXT",
    }

    for column_name, column_type in additions.items():
        if column_name not in columns:
            connection.execute(
                f"ALTER TABLE itt_indicator_submission_staging "
                f"ADD COLUMN {column_name} {column_type}"
            )


def _raw_existing_dashboard(connection):
    if not _table_exists(connection, "dashboard_data"):
        return pd.DataFrame(columns=RAW_COLUMNS)

    existing = pd.read_sql_query(
        "SELECT * FROM dashboard_data",
        connection,
    )

    if existing.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)

    for column_name in RAW_COLUMNS:
        if column_name not in existing.columns:
            existing[column_name] = pd.NA

    return existing[RAW_COLUMNS].copy()


def _approved_indicator_longitudinal(connection):
    indicators = connection.execute(
        """
        SELECT
            IndicatorSubmissionID,
            Project,
            ProposedIndicatorID,
            IndicatorName,
            UnitOfMeasure,
            Baseline,
            ProjectLifeTarget,
            Year1Target,
            Year2Target,
            Year3Target,
            Year4Target,
            Year5Target
        FROM itt_indicator_submission_staging
        WHERE ReviewStatus = 'Approved'
          AND COALESCE(
                DatasetInclusionStatus,
                'Pending Dataset Review'
              ) = 'Pending Dataset Review'
        ORDER BY IndicatorSubmissionID
        """
    ).fetchall()

    records = []
    merged_submission_ids = []
    without_targets = []

    for indicator in indicators:
        submission_id = int(indicator["IndicatorSubmissionID"])
        targets = connection.execute(
            """
            SELECT
                ProjectYear,
                Quarter,
                QuarterTarget,
                QuarterActual
            FROM itt_indicator_target_staging
            WHERE IndicatorSubmissionID = ?
            ORDER BY ProjectYear, Quarter
            """,
            (submission_id,),
        ).fetchall()

        if not targets:
            without_targets.append(submission_id)
            continue

        annual_targets = {
            1: indicator["Year1Target"],
            2: indicator["Year2Target"],
            3: indicator["Year3Target"],
            4: indicator["Year4Target"],
            5: indicator["Year5Target"],
        }

        for target in targets:
            year_number = int(target["ProjectYear"])
            quarter_number = int(target["Quarter"])

            records.append(
                {
                    "IndicatorID": indicator["ProposedIndicatorID"],
                    "Project": indicator["Project"],
                    "IndicatorName": indicator["IndicatorName"],
                    "Unit": indicator["UnitOfMeasure"],
                    "LoPTarget": indicator["ProjectLifeTarget"],
                    "Baseline": indicator["Baseline"],
                    "Year": year_number,
                    "Quarter": quarter_number,
                    "PeriodIndex": ((year_number - 1) * 4) + quarter_number,
                    "PeriodLabel": f"Y{year_number}Q{quarter_number}",
                    "QuarterTarget": target["QuarterTarget"],
                    "QuarterActual": target["QuarterActual"],
                    "AnnualTarget": annual_targets.get(year_number),
                    "Year 1 Target": indicator["Year1Target"],
                    "Year 2 Target": indicator["Year2Target"],
                    "Year 3 Target": indicator["Year3Target"],
                    " Year 4 target": indicator["Year4Target"],
                    " Year 5 target": indicator["Year5Target"],
                }
            )

        merged_submission_ids.append(submission_id)

    return (
        pd.DataFrame(records, columns=RAW_COLUMNS),
        merged_submission_ids,
        without_targets,
    )


def merge_approved_sources_into_longitudinal(
    uploaded_long_df,
    uploaded_itt_df,
    database_file,
):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row

    try:
        _ensure_indicator_tracking_columns(connection)
        connection.commit()

        existing_raw = _raw_existing_dashboard(connection)
        indicator_raw, indicator_ids, without_targets = (
            _approved_indicator_longitudinal(connection)
        )

        uploaded_raw = uploaded_long_df.copy()

        target_source_map = {
            "Year 1 Target": ["Year 1 Target"],
            "Year 2 Target": ["Year 2 Target"],
            "Year 3 Target": ["Year 3 Target"],
            " Year 4 target": [
                " Year 4 target",
                "Year 4 target",
                "Year 4 Target",
            ],
            " Year 5 target": [
                " Year 5 target",
                "Year 5 target",
                "Year 5 Target",
            ],
        }

        if (
            uploaded_itt_df is not None
            and not uploaded_itt_df.empty
            and "IndicatorID" in uploaded_itt_df.columns
        ):
            target_lookup = uploaded_itt_df[["IndicatorID"]].copy()

            for target_column, source_options in target_source_map.items():
                source_column = next(
                    (
                        option
                        for option in source_options
                        if option in uploaded_itt_df.columns
                    ),
                    None,
                )

                if source_column is None:
                    target_lookup[target_column] = pd.NA
                else:
                    target_lookup[target_column] = uploaded_itt_df[
                        source_column
                    ]

            target_lookup = target_lookup.drop_duplicates(
                subset=["IndicatorID"],
                keep="last",
            )

            uploaded_raw = uploaded_raw.merge(
                target_lookup,
                on="IndicatorID",
                how="left",
                validate="many_to_one",
            )

        for column_name in RAW_COLUMNS:
            if column_name not in uploaded_raw.columns:
                uploaded_raw[column_name] = pd.NA

        uploaded_raw = uploaded_raw[RAW_COLUMNS].copy()

        combined_raw = pd.concat(
            [existing_raw, uploaded_raw, indicator_raw],
            ignore_index=True,
            sort=False,
        )

        key_columns = [
            "Project",
            "IndicatorID",
            "Year",
            "Quarter",
        ]

        combined_raw = (
            combined_raw
            .drop_duplicates(
                subset=key_columns,
                keep="last",
            )
            .reset_index(drop=True)
        )

        portal_rows = connection.execute(
            """
            SELECT
                PortalApprovalID,
                IndicatorID,
                ProjectYear,
                Quarter,
                ApprovedTarget,
                ApprovedActual
            FROM portal_approved_staging
            WHERE DatasetInclusionStatus = 'Pending Dataset Review'
            ORDER BY PortalApprovalID
            """
        ).fetchall()

        merged_portal_ids = []
        unmatched_portal_ids = []

        for portal_row in portal_rows:
            indicator_id = str(portal_row["IndicatorID"]).strip()
            year_number = int(portal_row["ProjectYear"])
            quarter_number = int(portal_row["Quarter"])

            mask = (
                combined_raw["IndicatorID"].astype(str).str.strip()
                == indicator_id
            ) & (
                pd.to_numeric(
                    combined_raw["Year"],
                    errors="coerce",
                ) == year_number
            ) & (
                pd.to_numeric(
                    combined_raw["Quarter"],
                    errors="coerce",
                ) == quarter_number
            )

            if not mask.any():
                unmatched_portal_ids.append(
                    int(portal_row["PortalApprovalID"])
                )
                continue

            combined_raw.loc[
                mask,
                "QuarterTarget",
            ] = portal_row["ApprovedTarget"]

            combined_raw.loc[
                mask,
                "QuarterActual",
            ] = portal_row["ApprovedActual"]

            merged_portal_ids.append(
                int(portal_row["PortalApprovalID"])
            )

        audit = {
            "portal_ids": merged_portal_ids,
            "unmatched_portal_ids": unmatched_portal_ids,
            "indicator_submission_ids": indicator_ids,
            "indicators_without_targets": without_targets,
            "existing_rows": len(existing_raw),
        }

        return combined_raw, audit

    finally:
        connection.close()


def finalize_approved_sources(
    database_file,
    audit,
    included_by,
):
    connection = sqlite3.connect(database_file)

    try:
        connection.execute("BEGIN")

        portal_ids = audit.get("portal_ids", [])
        if portal_ids:
            placeholders = ",".join("?" for _ in portal_ids)
            connection.execute(
                f"""
                UPDATE portal_approved_staging
                SET DatasetInclusionStatus = 'Included in Dataset'
                WHERE PortalApprovalID IN ({placeholders})
                """,
                tuple(portal_ids),
            )

        indicator_ids = audit.get(
            "indicator_submission_ids",
            [],
        )
        if indicator_ids:
            placeholders = ",".join("?" for _ in indicator_ids)
            included_at = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            connection.execute(
                f"""
                UPDATE itt_indicator_submission_staging
                SET
                    DatasetInclusionStatus = 'Included in Dataset',
                    DatasetIncludedAt = ?,
                    DatasetIncludedBy = ?
                WHERE IndicatorSubmissionID IN ({placeholders})
                """,
                (
                    included_at,
                    included_by,
                    *indicator_ids,
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

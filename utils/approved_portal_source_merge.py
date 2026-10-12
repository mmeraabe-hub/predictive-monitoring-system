import sqlite3

import pandas as pd


def _table_columns(connection, table_name):
    return {
        row[1]
        for row in connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }


def _ensure_indicator_dataset_columns(connection):
    columns = _table_columns(
        connection,
        "itt_indicator_submission_staging",
    )

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


def merge_approved_portal_sources_into_itt(
    itt_df,
    database_file,
):
    """
    Merge approved quarterly portal updates and approved new
    indicators into the reconstructed wide ITT before longitudinal
    transformation and feature engineering.
    """
    combined_itt = itt_df.copy()

    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row

    try:
        _ensure_indicator_dataset_columns(connection)
        connection.commit()

        portal_updates = connection.execute(
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

        portal_ids = []
        unmatched_portal_ids = []

        for update in portal_updates:
            indicator_id = str(update["IndicatorID"])
            year_number = int(update["ProjectYear"])
            quarter_number = int(update["Quarter"])
            target_column = (
                f"Y{year_number}_Q{quarter_number}_Target"
            )
            actual_column = (
                f"Y{year_number}_Q{quarter_number}_Actual"
            )

            if target_column not in combined_itt.columns:
                combined_itt[target_column] = pd.NA
            if actual_column not in combined_itt.columns:
                combined_itt[actual_column] = pd.NA

            indicator_mask = (
                combined_itt["IndicatorID"]
                .astype(str)
                .str.strip()
                == indicator_id.strip()
            )

            if not indicator_mask.any():
                unmatched_portal_ids.append(
                    int(update["PortalApprovalID"])
                )
                continue

            combined_itt.loc[
                indicator_mask,
                target_column,
            ] = update["ApprovedTarget"]

            combined_itt.loc[
                indicator_mask,
                actual_column,
            ] = update["ApprovedActual"]

            portal_ids.append(
                int(update["PortalApprovalID"])
            )

        approved_indicators = connection.execute(
            """
            SELECT
                IndicatorSubmissionID,
                Project,
                ProjectCode,
                ProposedIndicatorID,
                IndicatorName,
                ResultLevelOriginal,
                ResultLevelStandard,
                LifeProjectYear,
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

        indicator_submission_ids = []
        new_indicator_rows = []
        indicators_without_targets = []

        for indicator in approved_indicators:
            submission_id = int(
                indicator["IndicatorSubmissionID"]
            )

            target_rows = connection.execute(
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

            if not target_rows:
                indicators_without_targets.append(submission_id)
                continue

            wide_row = {
                "IndicatorID": indicator["ProposedIndicatorID"],
                "Project": indicator["Project"],
                "ProjectCode": indicator["ProjectCode"],
                "Indicators ": indicator["IndicatorName"],
                "Unit of Measure": indicator["UnitOfMeasure"],
                "Project Life Target": indicator["ProjectLifeTarget"],
                "Baseline": indicator["Baseline"],
                "Result Level Original": indicator[
                    "ResultLevelOriginal"
                ],
                "Result Level Standard": indicator[
                    "ResultLevelStandard"
                ],
            }

            for year_number in range(1, 6):
                wide_row[f"Year {year_number} Target"] = indicator[
                    f"Year{year_number}Target"
                ]

            for target in target_rows:
                year_number = int(target["ProjectYear"])
                quarter_number = int(target["Quarter"])
                wide_row[
                    f"Y{year_number}_Q{quarter_number}_Target"
                ] = target["QuarterTarget"]
                wide_row[
                    f"Y{year_number}_Q{quarter_number}_Actual"
                ] = target["QuarterActual"]

            new_indicator_rows.append(wide_row)
            indicator_submission_ids.append(submission_id)

        if new_indicator_rows:
            new_indicator_df = pd.DataFrame(new_indicator_rows)
            combined_itt = pd.concat(
                [combined_itt, new_indicator_df],
                ignore_index=True,
                sort=False,
            )

        if "IndicatorID" in combined_itt.columns:
            combined_itt = (
                combined_itt
                .drop_duplicates(
                    subset=["IndicatorID"],
                    keep="last",
                )
                .reset_index(drop=True)
            )

        audit = {
            "portal_ids": portal_ids,
            "unmatched_portal_ids": unmatched_portal_ids,
            "indicator_submission_ids": indicator_submission_ids,
            "indicators_without_targets": indicators_without_targets,
        }

        return combined_itt, audit

    finally:
        connection.close()


def finalize_approved_portal_sources(
    database_file,
    audit,
    included_by,
    included_at,
):
    """
    Mark only successfully merged sources as included after the
    combined ETL has written dashboard_data_staging successfully.
    """
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

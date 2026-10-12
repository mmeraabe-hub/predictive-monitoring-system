import sqlite3
import pandas as pd

connection = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    print("\n==============================")
    print("APPROVED INDICATORS")
    print("==============================")

    approved_indicators = pd.read_sql_query(
        """
        SELECT
            IndicatorSubmissionID,
            ProposedIndicatorID,
            IndicatorName,
            ReviewStatus,
            DatasetInclusionStatus,
            Year1Target,
            Year2Target,
            Year3Target,
            Year4Target,
            Year5Target
        FROM itt_indicator_submission_staging
        WHERE ReviewStatus = 'Approved'
        ORDER BY IndicatorSubmissionID
        """,
        connection,
    )

    if approved_indicators.empty:
        print("No approved indicators found.")
    else:
        print(
            approved_indicators.to_string(
                index=False
            )
        )

    print("\n==============================")
    print("QUARTER TARGET ROWS")
    print("==============================")

    indicator_targets = pd.read_sql_query(
        """
        SELECT
            IndicatorSubmissionID,
            ProposedIndicatorID,
            ProjectYear,
            Quarter,
            QuarterTarget,
            QuarterActual
        FROM itt_indicator_target_staging
        WHERE IndicatorSubmissionID IN (
            SELECT IndicatorSubmissionID
            FROM itt_indicator_submission_staging
            WHERE ReviewStatus = 'Approved'
        )
        ORDER BY
            IndicatorSubmissionID,
            ProjectYear,
            Quarter
        """,
        connection,
    )

    if indicator_targets.empty:
        print(
            "No target rows found."
        )
    else:
        print(
            indicator_targets.to_string(
                index=False
            )
        )

    print("\n==============================")
    print("PENDING PORTAL UPDATES")
    print("==============================")

    pending_portal_updates = pd.read_sql_query(
        """
        SELECT
            PortalApprovalID,
            IndicatorID,
            ProjectYear,
            Quarter,
            ApprovedTarget,
            ApprovedActual,
            DatasetInclusionStatus
        FROM portal_approved_staging
        WHERE DatasetInclusionStatus =
            'Pending Dataset Review'
        ORDER BY PortalApprovalID
        """,
        connection,
    )

    if pending_portal_updates.empty:
        print(
            "No pending portal updates."
        )
    else:
        print(
            pending_portal_updates.to_string(
                index=False
            )
        )

    print("\n==============================")
    print("PORTAL INDICATORS FOUND IN DASHBOARD_DATA")
    print("==============================")

    production_matches = pd.read_sql_query(
        """
        SELECT DISTINCT
            IndicatorID,
            IndicatorName,
            Project
        FROM dashboard_data
        WHERE IndicatorID IN (
            SELECT IndicatorID
            FROM portal_approved_staging
            WHERE DatasetInclusionStatus =
                'Pending Dataset Review'
        )
        ORDER BY IndicatorID
        """,
        connection,
    )

    if production_matches.empty:
        print(
            "No matching production indicators found."
        )
    else:
        print(
            production_matches.to_string(
                index=False
            )
        )

finally:

    connection.close()
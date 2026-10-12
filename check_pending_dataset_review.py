import sqlite3

connection = sqlite3.connect(
    "predictive_monitoring.db"
)

try:
    print(
        "Pending portal quarterly updates:"
    )

    portal_rows = connection.execute(
        """
        SELECT
            PortalApprovalID,
            IndicatorID,
            ProjectYear,
            Quarter,
            DatasetInclusionStatus
        FROM portal_approved_staging
        WHERE DatasetInclusionStatus =
            'Pending Dataset Review'
        ORDER BY PortalApprovalID
        """
    ).fetchall()

    for row in portal_rows:
        print(row)

    print(
        "\nPending approved new indicators:"
    )

    indicator_rows = connection.execute(
        """
        SELECT
            IndicatorSubmissionID,
            ProposedIndicatorID,
            ReviewStatus,
            DatasetInclusionStatus
        FROM itt_indicator_submission_staging
        WHERE ReviewStatus = 'Approved'
          AND COALESCE(
                DatasetInclusionStatus,
                'Pending Dataset Review'
              ) = 'Pending Dataset Review'
        ORDER BY IndicatorSubmissionID
        """
    ).fetchall()

    for row in indicator_rows:
        print(row)

    print(
        "\nPortal count:",
        len(portal_rows),
    )

    print(
        "New indicator count:",
        len(indicator_rows),
    )

finally:
    connection.close()
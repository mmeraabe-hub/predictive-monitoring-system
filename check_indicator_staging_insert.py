import sqlite3

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    print("\nApproved indicators:")

    rows = conn.execute(
        """
        SELECT
            IndicatorSubmissionID,
            ProposedIndicatorID,
            DatasetInclusionStatus
        FROM itt_indicator_submission_staging
        WHERE ReviewStatus = 'Approved'
        """
    ).fetchall()

    for row in rows:
        print(row)

    print("\nMatching rows in dashboard_data_staging:")

    rows = conn.execute(
        """
        SELECT
            IndicatorID,
            IndicatorName,
            Year,
            Quarter
        FROM dashboard_data_staging
        WHERE IndicatorID IN (
            'GG_112',
            'Forgive_001'
        )
        """
    ).fetchall()

    for row in rows:
        print(row)

finally:

    conn.close()
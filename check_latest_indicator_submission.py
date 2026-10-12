import sqlite3

connection = sqlite3.connect(
    "predictive_monitoring.db"
)

try:
    rows = connection.execute(
        """
        SELECT
            IndicatorSubmissionID,
            ProposedIndicatorID,
            IndicatorName,
            ReviewStatus,
            SubmittedBy,
            SubmittedAt
        FROM itt_indicator_submission_staging
        ORDER BY IndicatorSubmissionID DESC
        LIMIT 10
        """
    ).fetchall()

    print(
        "Latest new-indicator registrations:"
    )

    for row in rows:
        print(row)

finally:
    connection.close()
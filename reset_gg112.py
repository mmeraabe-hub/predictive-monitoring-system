import sqlite3

connection = sqlite3.connect(
    "predictive_monitoring.db"
)

try:
    connection.execute(
        """
        UPDATE itt_indicator_submission_staging
        SET
            DatasetInclusionStatus =
                'Pending Dataset Review',
            DatasetIncludedAt = NULL,
            DatasetIncludedBy = NULL
        WHERE ProposedIndicatorID = 'GG_112'
        """
    )

    connection.commit()

    print(
        "GG_112 reset successfully."
    )

finally:
    connection.close()
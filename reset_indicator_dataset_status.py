import sqlite3

connection = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    connection.execute(
        """
        UPDATE itt_indicator_submission_staging
        SET
            DatasetInclusionStatus = 'Pending Dataset Review',
            DatasetIncludedAt = NULL,
            DatasetIncludedBy = NULL
        WHERE ReviewStatus = 'Approved'
        """
    )

    connection.execute(
        """
        UPDATE portal_approved_staging
        SET
            DatasetInclusionStatus = 'Pending Dataset Review'
        WHERE DatasetInclusionStatus = 'Included in Dataset'
        """
    )

    connection.commit()

    print(
        "Dataset review statuses reset successfully."
    )

finally:

    connection.close()
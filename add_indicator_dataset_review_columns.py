import sqlite3

DB_FILE = "predictive_monitoring.db"

conn = sqlite3.connect(DB_FILE)

try:

    columns = [
        row[1]
        for row in conn.execute(
            """
            PRAGMA table_info(
                itt_indicator_submission_staging
            )
            """
        ).fetchall()
    ]

    if "DatasetInclusionStatus" not in columns:

        conn.execute(
            """
            ALTER TABLE
                itt_indicator_submission_staging
            ADD COLUMN
                DatasetInclusionStatus TEXT
            """
        )

    if "DatasetIncludedAt" not in columns:

        conn.execute(
            """
            ALTER TABLE
                itt_indicator_submission_staging
            ADD COLUMN
                DatasetIncludedAt TEXT
            """
        )

    if "DatasetIncludedBy" not in columns:

        conn.execute(
            """
            ALTER TABLE
                itt_indicator_submission_staging
            ADD COLUMN
                DatasetIncludedBy TEXT
            """
        )

    conn.execute(
        """
        UPDATE
            itt_indicator_submission_staging
        SET
            DatasetInclusionStatus =
                'Pending Dataset Review'
        WHERE ReviewStatus = 'Approved'
          AND DatasetInclusionStatus IS NULL
        """
    )

    conn.commit()

    print(
        "Indicator dataset-review columns created successfully."
    )

finally:

    conn.close()
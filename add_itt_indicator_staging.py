import sqlite3


DATABASE_PATH = "predictive_monitoring.db"


def create_indicator_staging_tables():
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        cursor = connection.cursor()

        # ==================================================
        # NEW INDICATOR REGISTRATION STAGING
        # ==================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS
            itt_indicator_submission_staging (
                IndicatorSubmissionID INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                Project TEXT NOT NULL,
                ProjectCode TEXT NOT NULL,

                ProposedIndicatorID TEXT NOT NULL,
                IndicatorName TEXT NOT NULL,

                ResultLevelOriginal TEXT,
                ResultLevelStandard TEXT,

                LifeProjectYear INTEGER NOT NULL,
                UnitOfMeasure TEXT NOT NULL,

                Baseline REAL,
                ProjectLifeTarget REAL NOT NULL,

                Year1Target REAL,
                Year2Target REAL,
                Year3Target REAL,
                Year4Target REAL,
                Year5Target REAL,

                SubmittedBy TEXT,
                SubmittedAt TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                ReviewStatus TEXT NOT NULL
                    DEFAULT 'Pending',

                ReviewedBy TEXT,
                ReviewedAt TEXT,
                ReviewComment TEXT,

                CHECK (
                    LifeProjectYear BETWEEN 1 AND 5
                ),

                CHECK (
                    ReviewStatus IN (
                        'Pending',
                        'Approved',
                        'Rejected',
                        'Returned'
                    )
                )
            )
            """
        )

        # ==================================================
        # QUARTERLY TARGETS FOR NEW INDICATORS
        # ==================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS
            itt_indicator_target_staging (
                TargetStagingID INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                IndicatorSubmissionID INTEGER NOT NULL,

                ProposedIndicatorID TEXT NOT NULL,
                ProjectCode TEXT NOT NULL,

                ProjectYear INTEGER NOT NULL,
                Quarter INTEGER NOT NULL,

                QuarterTarget REAL NOT NULL,

                CreatedAt TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    IndicatorSubmissionID
                )
                    REFERENCES
                    itt_indicator_submission_staging (
                        IndicatorSubmissionID
                    )
                    ON DELETE CASCADE,

                UNIQUE (
                    IndicatorSubmissionID,
                    ProjectYear,
                    Quarter
                ),

                CHECK (
                    ProjectYear BETWEEN 1 AND 5
                ),

                CHECK (
                    Quarter BETWEEN 1 AND 4
                )
            )
            """
        )

        # ==================================================
        # PREVENT DUPLICATE PENDING INDICATOR IDS
        # ==================================================

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_unique_pending_indicator_id
            ON itt_indicator_submission_staging (
                ProposedIndicatorID
            )
            WHERE ReviewStatus = 'Pending'
            """
        )

        # ==================================================
        # PREVENT DUPLICATE PENDING INDICATOR NAMES
        # WITHIN THE SAME PROJECT
        # ==================================================

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_unique_pending_indicator_name
            ON itt_indicator_submission_staging (
                ProjectCode,
                IndicatorName
            )
            WHERE ReviewStatus = 'Pending'
            """
        )

        # ==================================================
        # QUERY PERFORMANCE INDEXES
        # ==================================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_indicator_submission_status
            ON itt_indicator_submission_staging (
                ReviewStatus,
                SubmittedAt
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_indicator_submission_project
            ON itt_indicator_submission_staging (
                ProjectCode,
                ProposedIndicatorID
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_indicator_target_submission
            ON itt_indicator_target_staging (
                IndicatorSubmissionID,
                ProjectYear,
                Quarter
            )
            """
        )

        connection.commit()

        print(
            "ITT indicator-registration staging tables "
            "created successfully."
        )

        tables_to_check = [
            "itt_indicator_submission_staging",
            "itt_indicator_target_staging",
        ]

        for table_name in tables_to_check:
            row_count = cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {table_name}
                """
            ).fetchone()[0]

            print(
                f"{table_name}: {row_count} records"
            )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_indicator_staging_tables()
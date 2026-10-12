import sqlite3


DATABASE_PATH = "predictive_monitoring.db"


def create_itt_tables():
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        cursor = connection.cursor()

        # ==================================================
        # 1. INDICATOR MASTER
        # ==================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS itt_indicator_master (
                IndicatorID TEXT PRIMARY KEY,
                Project TEXT NOT NULL,
                ProjectCode TEXT NOT NULL,
                IndicatorName TEXT NOT NULL,
                ResultLevelOriginal TEXT,
                ResultLevelStandard TEXT,
                LifeProjectYear INTEGER,
                UnitOfMeasure TEXT,
                ProjectLifeTarget REAL,
                Baseline REAL,
                Year1Target REAL,
                Year2Target REAL,
                Year3Target REAL,
                Year4Target REAL,
                Year5Target REAL,
                RecordStatus TEXT NOT NULL DEFAULT 'Active',
                CreatedBy TEXT,
                CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UpdatedBy TEXT,
                UpdatedAt TEXT
            )
            """
        )

        # ==================================================
        # 2. QUARTERLY PRODUCTION DATA
        # ==================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS itt_quarterly_data (
                QuarterlyRecordID INTEGER PRIMARY KEY AUTOINCREMENT,
                Project TEXT NOT NULL,
                ProjectCode TEXT NOT NULL,
                IndicatorID TEXT NOT NULL,
                ProjectYear INTEGER NOT NULL,
                Quarter INTEGER NOT NULL,
                QuarterTarget REAL,
                QuarterActual REAL,
                ApprovedSubmissionID INTEGER,
                UpdatedBy TEXT,
                UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (IndicatorID)
                    REFERENCES itt_indicator_master (IndicatorID),

                UNIQUE (
                    ProjectCode,
                    IndicatorID,
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
        # 3. QUARTERLY SUBMISSION STAGING
        # ==================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS itt_quarterly_submission_staging (
                SubmissionID INTEGER PRIMARY KEY AUTOINCREMENT,
                Project TEXT NOT NULL,
                ProjectCode TEXT NOT NULL,
                IndicatorID TEXT NOT NULL,
                ProjectYear INTEGER NOT NULL,
                Quarter INTEGER NOT NULL,

                CurrentTarget REAL,
                CurrentActual REAL,

                ProposedTarget REAL,
                ProposedActual REAL,

                SubmissionType TEXT NOT NULL,
                ChangeReason TEXT,

                SubmittedBy TEXT,
                SubmittedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                ReviewStatus TEXT NOT NULL DEFAULT 'Pending',
                ReviewedBy TEXT,
                ReviewedAt TEXT,
                ReviewComment TEXT,

                FOREIGN KEY (IndicatorID)
                    REFERENCES itt_indicator_master (IndicatorID),

                CHECK (
                    ProjectYear BETWEEN 1 AND 5
                ),

                CHECK (
                    Quarter BETWEEN 1 AND 4
                ),

                CHECK (
                    SubmissionType IN (
                        'New Quarter',
                        'Update Existing Quarter'
                    )
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
        # 4. AUDIT HISTORY
        # ==================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS itt_quarterly_audit_history (
                AuditID INTEGER PRIMARY KEY AUTOINCREMENT,
                SubmissionID INTEGER NOT NULL,
                Project TEXT NOT NULL,
                ProjectCode TEXT NOT NULL,
                IndicatorID TEXT NOT NULL,
                ProjectYear INTEGER NOT NULL,
                Quarter INTEGER NOT NULL,

                PreviousTarget REAL,
                PreviousActual REAL,

                ApprovedTarget REAL,
                ApprovedActual REAL,

                SubmissionType TEXT NOT NULL,
                ChangeReason TEXT,

                SubmittedBy TEXT,
                ApprovedBy TEXT,
                ApprovedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (SubmissionID)
                    REFERENCES itt_quarterly_submission_staging (
                        SubmissionID
                    ),

                FOREIGN KEY (IndicatorID)
                    REFERENCES itt_indicator_master (
                        IndicatorID
                    )
            )
            """
        )

        # ==================================================
        # 5. PREVENT MULTIPLE PENDING SUBMISSIONS
        # ==================================================

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_one_pending_itt_submission
            ON itt_quarterly_submission_staging (
                ProjectCode,
                IndicatorID,
                ProjectYear,
                Quarter
            )
            WHERE ReviewStatus = 'Pending'
            """
        )

        # ==================================================
        # 6. QUERY PERFORMANCE INDEXES
        # ==================================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_itt_indicator_project
            ON itt_indicator_master (
                ProjectCode,
                IndicatorID
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_itt_quarterly_period
            ON itt_quarterly_data (
                ProjectCode,
                IndicatorID,
                ProjectYear,
                Quarter
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_itt_submission_status
            ON itt_quarterly_submission_staging (
                ReviewStatus,
                SubmittedAt
            )
            """
        )

        connection.commit()

        print("ITT data-entry tables created successfully.")

        table_names = [
            "itt_indicator_master",
            "itt_quarterly_data",
            "itt_quarterly_submission_staging",
            "itt_quarterly_audit_history",
        ]

        for table_name in table_names:
            row_count = cursor.execute(
                f"SELECT COUNT(*) FROM {table_name}"
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
    create_itt_tables()
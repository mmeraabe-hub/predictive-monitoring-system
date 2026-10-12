import sqlite3

DATABASE_PATH = "predictive_monitoring.db"


conn = sqlite3.connect(
    DATABASE_PATH
)

cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS
    portal_approved_staging (

        PortalApprovalID INTEGER
        PRIMARY KEY AUTOINCREMENT,

        SubmissionID INTEGER,

        Project TEXT,
        ProjectCode TEXT,

        IndicatorID TEXT,

        ProjectYear INTEGER,
        Quarter INTEGER,

        CurrentTarget REAL,
        CurrentActual REAL,

        ApprovedTarget REAL,
        ApprovedActual REAL,

        SubmissionType TEXT,

        SubmittedBy TEXT,
        SubmittedAt TEXT,

        ApprovedBy TEXT,
        ApprovedAt TEXT,

        ApprovalComment TEXT,

        DatasetInclusionStatus TEXT
        DEFAULT 'Pending Dataset Review'
    )
    """
)

conn.commit()

print(
    "portal_approved_staging created successfully."
)

conn.close()
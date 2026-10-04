import sqlite3

DB_FILE = "predictive_monitoring.db"

conn = sqlite3.connect(DB_FILE)

try:

    conn.execute("""
    CREATE TABLE IF NOT EXISTS dashboard_data_staging AS
    SELECT *
    FROM dashboard_data
    WHERE 1 = 0
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS model_performance_staging AS
    SELECT *
    FROM model_performance
    WHERE 1 = 0
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS training_run_staging
    (
        RunID INTEGER PRIMARY KEY AUTOINCREMENT,

        UploadBatchID TEXT,

        RunStartedUTC TEXT,

        RunFinishedUTC TEXT,

        ProjectsBefore INTEGER,

        ProjectsAfter INTEGER,

        DashboardRowsBefore INTEGER,

        DashboardRowsAfter INTEGER,

        RowsAdded INTEGER,

        TrainingRows INTEGER,

        TestingRows INTEGER,

        ModelsEvaluated INTEGER,

        RecommendedModel TEXT,

        RecommendedRMSE REAL,

        RecommendedMAE REAL,

        Status TEXT
    )
    """)

    conn.commit()

    print("SUCCESS - staging tables created")

finally:

    conn.close()
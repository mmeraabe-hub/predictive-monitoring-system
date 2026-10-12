import sqlite3

DB_FILE = "predictive_monitoring.db"

conn = sqlite3.connect(DB_FILE)

try:

    tables_to_clear = [

        "uploaded_itt_staging",
        "itt_upload_batches",
        "dataset_approval_log",

        "itt_quarterly_submission_staging",
        "portal_approved_staging",

        "itt_indicator_submission_staging",
        "itt_indicator_target_staging",

        "prediction_archive",
        "prediction_archive_staging",

        "forecast_verification_metrics",
        "forecast_verification_metrics_staging",

        "forecast_verification_by_project",
        "forecast_verification_by_project_staging",

        "model_performance_staging",
        "training_run_staging",

        "dashboard_data_staging",

    ]

    for table_name in tables_to_clear:

        try:

            conn.execute(
                f"DELETE FROM {table_name}"
            )

            print(
                f"Cleared: {table_name}"
            )

        except Exception as error:

            print(
                f"Skipped {table_name}: {error}"
            )

    conn.commit()

    print(
        "\nAll transactional data cleared."
    )

finally:

    conn.close()
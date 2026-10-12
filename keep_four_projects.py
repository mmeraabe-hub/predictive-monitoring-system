import sqlite3

KEEP = [
    "CRRP",
    "RFSA",
    "Girls Gain",
    "Regreening Africa I"
]

conn = sqlite3.connect(
    "predictive_monitoring.db"
)

try:

    tables = [
        "dashboard_data",
        "dashboard_data_staging",
        "prediction_archive",
        "prediction_archive_staging",
        "forecast_verification_by_project",
        "forecast_verification_by_project_staging"
    ]

    for table_name in tables:

        try:

            conn.execute(
                f"""
                DELETE FROM {table_name}
                WHERE Project NOT IN (
                    ?, ?, ?, ?
                )
                """,
                KEEP,
            )

            print(
                f"Cleaned {table_name}"
            )

        except Exception as error:

            print(
                f"Skipped {table_name}: {error}"
            )

    conn.commit()

    print(
        "\nCleanup complete."
    )

finally:

    conn.close()
import sqlite3


DATABASE_PATH = "predictive_monitoring.db"


connection = sqlite3.connect(
    DATABASE_PATH
)

try:
    columns = [
        row[1]
        for row in connection.execute(
            """
            PRAGMA table_info(
                itt_indicator_target_staging
            )
            """
        ).fetchall()
    ]

    if "QuarterActual" not in columns:
        connection.execute(
            """
            ALTER TABLE
                itt_indicator_target_staging
            ADD COLUMN
                QuarterActual REAL
            """
        )

        connection.commit()

        print(
            "QuarterActual added successfully."
        )

    else:
        print(
            "QuarterActual already exists."
        )

finally:
    connection.close()
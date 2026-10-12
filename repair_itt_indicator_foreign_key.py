import sqlite3


DATABASE_PATH = "predictive_monitoring.db"


connection = sqlite3.connect(
    DATABASE_PATH
)

try:
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    # --------------------------------------------------
    # VERIFY THE PARENT TABLE
    # --------------------------------------------------

    table_exists = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'itt_indicator_master'
        """
    ).fetchone()[0]

    if not table_exists:
        raise RuntimeError(
            "itt_indicator_master does not exist."
        )

    columns = [
        row[1]
        for row in connection.execute(
            """
            PRAGMA table_info(
                itt_indicator_master
            )
            """
        ).fetchall()
    ]

    if "IndicatorID" not in columns:
        raise RuntimeError(
            "itt_indicator_master does not contain "
            "the IndicatorID column."
        )

    # --------------------------------------------------
    # CHECK FOR MISSING INDICATOR IDS
    # --------------------------------------------------

    missing_id_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM itt_indicator_master
        WHERE IndicatorID IS NULL
           OR TRIM(IndicatorID) = ''
        """
    ).fetchone()[0]

    if missing_id_count > 0:
        raise RuntimeError(
            f"Cannot create the unique index because "
            f"{missing_id_count} repository records have "
            f"a missing IndicatorID."
        )

    # --------------------------------------------------
    # CHECK FOR DUPLICATE INDICATOR IDS
    # --------------------------------------------------

    duplicate_ids = connection.execute(
        """
        SELECT
            IndicatorID,
            COUNT(*) AS RecordCount
        FROM itt_indicator_master
        GROUP BY IndicatorID
        HAVING COUNT(*) > 1
        ORDER BY IndicatorID
        """
    ).fetchall()

    if duplicate_ids:
        print(
            "Duplicate Indicator IDs were found:"
        )

        for indicator_id, record_count in duplicate_ids:
            print(
                f"{indicator_id}: "
                f"{record_count} records"
            )

        raise RuntimeError(
            "The foreign-key repair was stopped. "
            "Duplicate Indicator IDs must be resolved first."
        )

    # --------------------------------------------------
    # CREATE THE REQUIRED UNIQUE PARENT KEY
    # --------------------------------------------------

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_itt_indicator_master_indicator_id
        ON itt_indicator_master (
            IndicatorID
        )
        """
    )

    connection.commit()

    # --------------------------------------------------
    # VERIFY THE RESULT
    # --------------------------------------------------

    indicator_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM itt_indicator_master
        """
    ).fetchone()[0]

    index_rows = connection.execute(
        """
        PRAGMA index_list(
            itt_indicator_master
        )
        """
    ).fetchall()

    unique_index_found = False

    for index_row in index_rows:
        index_name = index_row[1]
        is_unique = index_row[2]

        if (
            index_name
            == "idx_itt_indicator_master_indicator_id"
            and is_unique == 1
        ):
            unique_index_found = True
            break

    if not unique_index_found:
        raise RuntimeError(
            "The required unique index was not created."
        )

    print(
        "ITT IndicatorID foreign-key repair completed."
    )

    print(
        f"Indicators preserved: {indicator_count}"
    )

    print(
        "Unique IndicatorID index: verified"
    )

finally:
    connection.close()
import sqlite3


def include_approved_portal_items(
    database_file,
):
    conn = sqlite3.connect(
        database_file
    )

    try:

        portal_updates = conn.execute(
            """
            SELECT COUNT(*)
            FROM portal_approved_staging
            WHERE DatasetInclusionStatus =
                'Pending Dataset Review'
            """
        ).fetchone()[0]

        approved_indicators = conn.execute(
            """
            SELECT COUNT(*)
            FROM itt_indicator_submission_staging
            WHERE ReviewStatus = 'Approved'
            """
        ).fetchone()[0]

        conn.execute(
            """
            UPDATE portal_approved_staging
            SET DatasetInclusionStatus =
                'Included in Dataset'
            WHERE DatasetInclusionStatus =
                'Pending Dataset Review'
            """
        )

        conn.execute(
            """
            UPDATE itt_indicator_submission_staging
            SET DatasetInclusionStatus =
                'Included in Dataset'
            WHERE ReviewStatus = 'Approved'
            """
        )

        conn.commit()

        return {
            "portal_updates":
                portal_updates,
            "new_indicators":
                approved_indicators,
        }

    finally:

        conn.close()
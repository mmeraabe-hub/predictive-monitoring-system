
"""
Automation Logger

Phase 12D.1
"""

import sqlite3
from datetime import datetime, UTC


def log_automation_run(
    database_file,
    retraining_status,
    governance_status,
    recommended_original,
    recommended_capped,
    automation_type="Retraining+Governance",
    status="Completed",
    error_message=None
):

    with sqlite3.connect(database_file) as conn:

        conn.execute(
            """
            INSERT INTO automation_run_history (

                UploadBatchID,
                FileName,
                TriggerSource,

                RunStartUTC,
                RunEndUTC,

                Status,

                InputRows,
                TransformedRows,
                RowsInserted,
                RowsUpdated,
                RowsUnchanged,

                ErrorMessage,

                DryRun,

                RetrainingStatus,
                GovernanceStatus,

                RecommendedOriginalModel,
                RecommendedCappedModel,

                AutomationType

            )
            VALUES (

                ?, ?, ?,
                ?, ?,
                ?,
                ?, ?, ?, ?, ?,
                ?,
                ?,
                ?, ?,
                ?, ?,
                ?

            )
            """,
            (

                "SYSTEM_AUTOMATION",

                None,

                "Automation_Orchestrator",

                datetime.now(UTC).isoformat(),

                datetime.now(UTC).isoformat(),

                status,

                0,
                0,
                0,
                0,
                0,

                error_message,

                1,

                retraining_status,

                governance_status,

                recommended_original,

                recommended_capped,

                automation_type

            )
        )

        conn.commit()

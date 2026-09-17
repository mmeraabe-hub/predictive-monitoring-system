
"""
Automation Orchestrator

Phase 12C
Read-only orchestration layer.
"""

from datetime import datetime

from utils.retraining_engine import (
    run_retraining_pipeline
)

from utils.governance_preview import (
    create_governance_previews
)


def run_automation_pipeline(database_file):

    start_time = datetime.utcnow()

    retraining_result = run_retraining_pipeline(
        database_file=database_file,
        dataset_types=("Original", "Capped"),
        training_share=0.80,
        random_state=42
    )

    governance_result = create_governance_previews(
        database_file=database_file,
        evaluated_results=
        retraining_result["Performance"]
    )

    finish_time = datetime.utcnow()

    return {
        "Summary": {
            "Status": "Completed",
            "ReadOnly": True,
            "StartedUTC": str(start_time),
            "FinishedUTC": str(finish_time),
            "RetrainingStatus":
                retraining_result["Status"],
            "GovernanceStatus":
                governance_result["Status"]
        },
        "Retraining":
            retraining_result,
        "Governance":
            governance_result
    }

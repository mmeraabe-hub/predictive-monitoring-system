import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
from auth import require_login

current_user = require_login("itt.view")

user_roles = set(
    current_user.get(
        "roles",
        []
    )
)

is_admin = "Admin" in user_roles

is_data_entry = (
    "Data Entry" in user_roles
)

is_reviewer = (
    "Reviewer" in user_roles
)

can_enter_data = (
    is_admin
    or is_data_entry
)

can_review_submission = (
    is_admin
    or is_reviewer
)


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="ITT Data Entry Portal",
    page_icon="📝",
    layout="wide",
)

DATABASE_PATH = "predictive_monitoring.db"
# ==================================================
# FORM RESET STATE
# ==================================================

if "submission_form_version" not in st.session_state:
    st.session_state.submission_form_version = 0

if "review_form_version" not in st.session_state:
    st.session_state.review_form_version = 0

if "resubmit_form_version" not in st.session_state:
    st.session_state.resubmit_form_version = 0


def reset_submission_form():
    """
    Reset the quarterly actual submission form.
    """
    st.session_state.submission_form_version += 1
    st.cache_data.clear()
    st.rerun()


def reset_review_form():
    """
    Reset the Approve, Reject, and Return review form.
    """
    st.session_state.review_form_version += 1
    st.cache_data.clear()
    st.rerun()


def reset_resubmit_form():
    """
    Reset the returned-item resubmission form.
    """
    st.session_state.resubmit_form_version += 1
    st.cache_data.clear()
    st.rerun()

# ==================================================
# DATABASE HELPERS
# ==================================================

def get_connection():
    """
    Open the SQLite monitoring database.
    """
    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def table_exists(connection, table_name):
    """
    Return True when the requested table exists.
    """
    result = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()[0]

    return result > 0


def get_table_columns(connection, table_name):
    """
    Return the column names available in a table.
    """
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [
        row["name"]
        for row in rows
    ]


def safe_numeric(value):
    """
    Convert a database value to a float.
    """
    if value is None:
        return None

    try:
        numeric_value = float(value)

        if pd.isna(numeric_value):
            return None

        return numeric_value

    except (TypeError, ValueError):
        return None


def first_non_null(data, column_names):
    """
    Return the first non-null value from the listed columns.
    """
    if data is None:
        return None

    if isinstance(data, sqlite3.Row):
        available_columns = data.keys()

    else:
        available_columns = data.keys()

    for column_name in column_names:
        if column_name in available_columns:
            value = data[column_name]

            if value is not None and not pd.isna(value):
                return value

    return None


def format_value(value, unit=None):
    """
    Format a value using the indicator's approved unit.
    """
    numeric_value = safe_numeric(value)

    if numeric_value is None:
        return "Not available"

    unit_text = str(
        unit or ""
    ).strip().lower()

    percentage_terms = [
        "%",
        "percent",
        "percentage",
        "ratio",
    ]

    is_percentage = any(
        term in unit_text
        for term in percentage_terms
    )

    if is_percentage:
        if abs(numeric_value) <= 1.5:
            return f"{numeric_value:.1%}"

        return f"{numeric_value:.1f}%"

    if numeric_value.is_integer():
        return f"{int(numeric_value):,}"

    return f"{numeric_value:,.2f}"
def generate_next_indicator_id(
    project_code,
):
    """
    Generate the next available Indicator ID
    for the selected project.
    """

    connection = get_connection()

    try:

        existing_ids = []

        # Approved repository
        if table_exists(
            connection,
            "itt_indicator_master",
        ):

            repository_ids = connection.execute(
                """
                SELECT IndicatorID
                FROM itt_indicator_master
                WHERE ProjectCode = ?
                """,
                (
                    project_code,
                ),
            ).fetchall()

            existing_ids.extend(
                [
                    row["IndicatorID"]
                    for row in repository_ids
                    if row["IndicatorID"]
                ]
            )

        # Pending indicator requests
        if table_exists(
            connection,
            "itt_indicator_submission_staging",
        ):

            staging_ids = connection.execute(
                """
                SELECT ProposedIndicatorID
                FROM itt_indicator_submission_staging
                WHERE ProjectCode = ?
                """,
                (
                    project_code,
                ),
            ).fetchall()

            existing_ids.extend(
                [
                    row["ProposedIndicatorID"]
                    for row in staging_ids
                    if row["ProposedIndicatorID"]
                ]
            )

        highest_number = 0

        for indicator_id in existing_ids:

            try:

                indicator_number = int(
                    str(indicator_id)
                    .split("_")[-1]
                )

                highest_number = max(
                    highest_number,
                    indicator_number,
                )

            except Exception:
                continue

        next_number = highest_number + 1

        return (
            f"{project_code}_{next_number:03d}"
        )

    finally:

        connection.close()
def save_new_indicator_submission(
    project,
    project_code,
    indicator_id,
    indicator_name,
    result_level_original,
    result_level_standard,
    unit_of_measure,
    project_duration,
    baseline,
    lop_target,
    annual_targets,
    quarter_targets,
):
    """
    Save a new indicator request into staging.
    """

    connection = get_connection()

    try:

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            INSERT INTO
            itt_indicator_submission_staging (
                Project,
                ProjectCode,
                ProposedIndicatorID,
                IndicatorName,
                ResultLevelOriginal,
                ResultLevelStandard,
                LifeProjectYear,
                UnitOfMeasure,
                Baseline,
                ProjectLifeTarget,
                Year1Target,
                Year2Target,
                Year3Target,
                Year4Target,
                Year5Target,
                ReviewStatus
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                'Pending'
            )
            """,
            (
                project,
                project_code,
                indicator_id,
                indicator_name,
                result_level_original,
                result_level_standard,
                project_duration,
                unit_of_measure,
                baseline,
                lop_target,
                annual_targets.get(1),
                annual_targets.get(2),
                annual_targets.get(3),
                annual_targets.get(4),
                annual_targets.get(5),
            ),
        )

        indicator_submission_id = (
            cursor.lastrowid
        )

        for year_number, quarter_dict in (
            quarter_targets.items()
        ):

            for quarter_number, quarter_values in (
                quarter_dict.items()
            ):

                quarter_target = (
                    quarter_values.get(
                        "Target"
                    )
                )

                quarter_actual = (
                    quarter_values.get(
                        "Actual"
                    )
                )

                if quarter_target is not None:

                    quarter_target = float(
                        quarter_target
                    )

                if quarter_actual is not None:

                    quarter_actual = float(
                        quarter_actual
                    )

                connection.execute(
                    """
                    INSERT INTO
                    itt_indicator_target_staging (
                        IndicatorSubmissionID,
                        ProposedIndicatorID,
                        ProjectCode,
                        ProjectYear,
                        Quarter,
                        QuarterTarget,
                        QuarterActual
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        indicator_submission_id,
                        generated_indicator_id,
                        project_code,
                        int(year_number),
                        int(quarter_number),
                        quarter_target,
                        quarter_actual,
                    ),
                )
        connection.commit()

        return {
            "success": True,
            "submission_id":
                indicator_submission_id,
        }

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()
def load_result_level_standards():

    connection = get_connection()

    try:

        standards = []

        rows = connection.execute(
            """
            SELECT DISTINCT
                ResultLevelStandard
            FROM itt_indicator_submission_staging
            WHERE ResultLevelStandard IS NOT NULL
              AND TRIM(ResultLevelStandard) <> ''
            ORDER BY ResultLevelStandard
            """
        ).fetchall()

        standards.extend(
            [
                str(row["ResultLevelStandard"]).strip()
                for row in rows
            ]
        )

        return sorted(
            set(standards)
        )

    finally:

        connection.close()
def record_new_indicator_review(
    indicator_submission_id,
    review_action,
    reviewed_by,
    review_comment,
):
    """
    Record a review decision for a new indicator registration.
    """
    connection = get_connection()

    try:
        allowed_actions = {
            "Approve": "Approved",
            "Return for Correction": "Returned",
            "Reject": "Rejected",
        }

        if review_action not in allowed_actions:
            return {
                "success": False,
                "message": "Invalid review decision.",
            }

        new_status = allowed_actions[
            review_action
        ]

        current_record = connection.execute(
            """
            SELECT
                IndicatorSubmissionID,
                ReviewStatus
            FROM itt_indicator_submission_staging
            WHERE IndicatorSubmissionID = ?
            LIMIT 1
            """,
            (
                int(indicator_submission_id),
            ),
        ).fetchone()

        if current_record is None:
            return {
                "success": False,
                "message": (
                    "The selected indicator registration "
                    "could not be found."
                ),
            }

        if current_record["ReviewStatus"] != "Pending":
            return {
                "success": False,
                "message": (
                    "The selected indicator registration "
                    "is no longer pending."
                ),
            }

        reviewed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            UPDATE itt_indicator_submission_staging
            SET
                ReviewStatus = ?,
                ReviewedBy = ?,
                ReviewedAt = ?,
                ReviewComment = ?
            WHERE IndicatorSubmissionID = ?
              AND ReviewStatus = 'Pending'
            """,
            (
                new_status,
                reviewed_by,
                reviewed_at,
                review_comment,
                int(indicator_submission_id),
            ),
        )

        if cursor.rowcount == 0:
            connection.rollback()

            return {
                "success": False,
                "message": (
                    "The indicator registration could "
                    "not be updated."
                ),
            }

        connection.commit()

        return {
            "success": True,
            "status": new_status,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
# ==================================================
# INDICATOR REPOSITORY
# ==================================================

@st.cache_data
def load_indicator_repository():
    """
    Load approved indicators from itt_indicator_master.
    """
    connection = get_connection()

    try:
        if not table_exists(
            connection,
            "itt_indicator_master",
        ):
            return pd.DataFrame()

        repository_columns = get_table_columns(
            connection,
            "itt_indicator_master",
        )

        required_columns = [
            "IndicatorID",
            "Project",
            "IndicatorName",
            "ProjectCode",
        ]

        missing_columns = [
            column_name
            for column_name in required_columns
            if column_name not in repository_columns
        ]

        if missing_columns:
            raise RuntimeError(
                "itt_indicator_master is missing: "
                + ", ".join(missing_columns)
            )

        repository = pd.read_sql_query(
            """
            SELECT *
            FROM itt_indicator_master
            WHERE IndicatorID IS NOT NULL
              AND TRIM(IndicatorID) <> ''
              AND Project IS NOT NULL
              AND TRIM(Project) <> ''
              AND IndicatorName IS NOT NULL
              AND TRIM(IndicatorName) <> ''
            ORDER BY
                Project,
                IndicatorName,
                IndicatorID
            """,
            connection,
        )

        return repository

    finally:
        connection.close()


def get_repository_value(
    indicator_record,
    possible_columns,
):
    """
    Support both the simplified repository and full master schema.
    """
    for column_name in possible_columns:
        if column_name in indicator_record:
            value = indicator_record[column_name]

            if value is not None and not pd.isna(value):
                return value

    return None


# ==================================================
# APPROVED PERIOD DATA
# ==================================================

def get_itt_quarterly_record(
    connection,
    project_code,
    indicator_id,
    project_year,
    quarter,
):
    """
    Retrieve one approved ITT quarterly record.
    """
    if not table_exists(
        connection,
        "itt_quarterly_data",
    ):
        return None

    return connection.execute(
        """
        SELECT *
        FROM itt_quarterly_data
        WHERE ProjectCode = ?
          AND IndicatorID = ?
          AND ProjectYear = ?
          AND Quarter = ?
        LIMIT 1
        """,
        (
            project_code,
            indicator_id,
            int(project_year),
            int(quarter),
        ),
    ).fetchone()


def get_dashboard_period_record(
    connection,
    indicator_id,
    project_year,
    quarter,
):
    """
    Retrieve one approved reporting period from dashboard_data.
    """
    if not table_exists(
        connection,
        "dashboard_data",
    ):
        return None

    dashboard_columns = get_table_columns(
        connection,
        "dashboard_data",
    )

    required_columns = [
        "IndicatorID",
        "QuarterTarget",
        "QuarterActual",
    ]

    if any(
        column_name not in dashboard_columns
        for column_name in required_columns
    ):
        return None

    conditions = [
        "IndicatorID = ?"
    ]

    parameters = [
        indicator_id
    ]

    if "YearNumber" in dashboard_columns:
        conditions.append(
            "CAST(YearNumber AS INTEGER) = ?"
        )
        parameters.append(
            int(project_year)
        )

    elif "Year" in dashboard_columns:
        conditions.append(
            "CAST(Year AS INTEGER) = ?"
        )
        parameters.append(
            int(project_year)
        )

    else:
        return None

    if "QuarterNumber" in dashboard_columns:
        conditions.append(
            "CAST(QuarterNumber AS INTEGER) = ?"
        )
        parameters.append(
            int(quarter)
        )

    elif "Quarter" in dashboard_columns:
        conditions.append(
            """
            (
                CAST(Quarter AS INTEGER) = ?
                OR UPPER(TRIM(CAST(Quarter AS TEXT))) = ?
            )
            """
        )

        parameters.extend(
            [
                int(quarter),
                f"Q{int(quarter)}",
            ]
        )

    else:
        return None

    order_statement = ""

    if "PeriodIndex" in dashboard_columns:
        order_statement = (
            "ORDER BY PeriodIndex DESC"
        )

    query = f"""
        SELECT *
        FROM dashboard_data
        WHERE {' AND '.join(conditions)}
        {order_statement}
        LIMIT 1
    """

    return connection.execute(
        query,
        tuple(parameters),
    ).fetchone()


def get_current_period_values(
    project_code,
    indicator_id,
    project_year,
    quarter,
):
    """
    Retrieve approved target and actual values.

    ITT quarterly production is checked first.
    dashboard_data is used as the fallback source.
    """
    connection = get_connection()

    try:
        itt_record = get_itt_quarterly_record(
            connection,
            project_code,
            indicator_id,
            project_year,
            quarter,
        )

        dashboard_record = get_dashboard_period_record(
            connection,
            indicator_id,
            project_year,
            quarter,
        )

        quarter_target = first_non_null(
            itt_record,
            [
                "QuarterTarget",
            ],
        )

        quarter_actual = first_non_null(
            itt_record,
            [
                "QuarterActual",
            ],
        )

        if quarter_target is None:
            quarter_target = first_non_null(
                dashboard_record,
                [
                    "QuarterTarget",
                ],
            )

        if quarter_actual is None:
            quarter_actual = first_non_null(
                dashboard_record,
                [
                    "QuarterActual",
                ],
            )

        return {
            "QuarterTarget": safe_numeric(
                quarter_target
            ),
            "QuarterActual": safe_numeric(
                quarter_actual
            ),
        }

    finally:
        connection.close()


def get_annual_target(
    indicator_record,
    indicator_id,
    project_year,
):
    """
    Retrieve the annual target for the selected project year.
    """
    year_column_options = {
        1: [
            "Year1Target",
            "Year 1 Target",
        ],
        2: [
            "Year2Target",
            "Year 2 Target",
        ],
        3: [
            "Year3Target",
            "Year 3 Target",
        ],
        4: [
            "Year4Target",
            "Year 4 Target",
            "Year 4 target",
            " Year 4 target",
        ],
        5: [
            "Year5Target",
            "Year 5 Target",
            "Year 5 target",
            " Year 5 target",
        ],
    }

    repository_target = get_repository_value(
        indicator_record,
        year_column_options[
            int(project_year)
        ],
    )

    if repository_target is not None:
        return safe_numeric(
            repository_target
        )

    connection = get_connection()

    try:
        if not table_exists(
            connection,
            "dashboard_data",
        ):
            return None

        dashboard_columns = get_table_columns(
            connection,
            "dashboard_data",
        )

        possible_columns = [
            "AnnualTarget",
        ] + year_column_options[
            int(project_year)
        ]

        target_column = None

        for column_name in possible_columns:
            if column_name in dashboard_columns:
                target_column = column_name
                break

        if target_column is None:
            return None

        if "YearNumber" in dashboard_columns:
            row = connection.execute(
                f"""
                SELECT "{target_column}"
                FROM dashboard_data
                WHERE IndicatorID = ?
                  AND CAST(YearNumber AS INTEGER) = ?
                  AND "{target_column}" IS NOT NULL
                ORDER BY PeriodIndex DESC
                LIMIT 1
                """,
                (
                    indicator_id,
                    int(project_year),
                ),
            ).fetchone()

        else:
            row = connection.execute(
                f"""
                SELECT "{target_column}"
                FROM dashboard_data
                WHERE IndicatorID = ?
                  AND "{target_column}" IS NOT NULL
                LIMIT 1
                """,
                (indicator_id,),
            ).fetchone()

        if row is None:
            return None

        return safe_numeric(
            row[target_column]
        )

    finally:
        connection.close()


def build_year_progress(
    project_code,
    indicator_id,
    project_year,
):
    """
    Build the Q1-Q4 progress summary for one project year.
    """
    records = []

    for quarter_number in range(1, 5):
        period_values = get_current_period_values(
            project_code,
            indicator_id,
            project_year,
            quarter_number,
        )

        approved_actual = period_values[
            "QuarterActual"
        ]

        if approved_actual is None:
            reporting_status = "Not Reported"

        else:
            reporting_status = "Approved"

        records.append(
            {
                "Quarter": f"Q{quarter_number}",
                "Target": period_values[
                    "QuarterTarget"
                ],
                "Approved Actual": approved_actual,
                "Status": reporting_status,
            }
        )

    return pd.DataFrame(
        records
    )


# ==================================================
# STAGING SUBMISSIONS
# ==================================================
def load_pending_year_submissions(
    project_code,
    indicator_id,
    project_year,
):
    """
    Load pending quarterly submissions for the selected indicator year.
    """
    connection = get_connection()

    try:
        pending_submissions = pd.read_sql_query(
            """
            SELECT
                Quarter,
                ProposedTarget,
                ProposedActual,
                SubmissionID,
                SubmittedBy,
                SubmittedAt,
                ReviewStatus
            FROM itt_quarterly_submission_staging
            WHERE ProjectCode = ?
              AND IndicatorID = ?
              AND ProjectYear = ?
              AND ReviewStatus = 'Pending'
            ORDER BY
                Quarter,
                SubmissionID DESC
            """,
            connection,
            params=(
                project_code,
                indicator_id,
                int(project_year),
            ),
        )

        if pending_submissions.empty:
            return pending_submissions

        pending_submissions = (
            pending_submissions
            .drop_duplicates(
                subset=["Quarter"],
                keep="first",
            )
            .copy()
        )

        return pending_submissions

    finally:
        connection.close()
def get_pending_submission(
    project_code,
    indicator_id,
    project_year,
    quarter,
):
    """
    Retrieve a pending submission for the same period.
    """
    connection = get_connection()

    try:
        return connection.execute(
            """
            SELECT *
            FROM itt_quarterly_submission_staging
            WHERE ProjectCode = ?
              AND IndicatorID = ?
              AND ProjectYear = ?
              AND Quarter = ?
              AND ReviewStatus = 'Pending'
            ORDER BY SubmissionID DESC
            LIMIT 1
            """,
            (
                project_code,
                indicator_id,
                int(project_year),
                int(quarter),
            ),
        ).fetchone()

    finally:
        connection.close()


def save_quarterly_submission(
    project,
    project_code,
    indicator_id,
    project_year,
    quarter,
    current_target,
    current_actual,
    proposed_actual,
    change_reason,
    submitted_by,
):
    """
    Save a quarterly actual in the persistent review queue.
    """
    connection = get_connection()

    try:
        existing_pending = connection.execute(
            """
            SELECT SubmissionID
            FROM itt_quarterly_submission_staging
            WHERE ProjectCode = ?
              AND IndicatorID = ?
              AND ProjectYear = ?
              AND Quarter = ?
              AND ReviewStatus = 'Pending'
            LIMIT 1
            """,
            (
                project_code,
                indicator_id,
                int(project_year),
                int(quarter),
            ),
        ).fetchone()

        if existing_pending is not None:
            return {
                "success": False,
                "message": (
                    "A pending submission already exists "
                    "for this indicator and reporting period."
                ),
            }

        if current_actual is None:
            submission_type = "New Quarter"

        else:
            submission_type = (
                "Update Existing Quarter"
            )

        submitted_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            INSERT INTO itt_quarterly_submission_staging (
                Project,
                ProjectCode,
                IndicatorID,
                ProjectYear,
                Quarter,
                CurrentTarget,
                CurrentActual,
                ProposedTarget,
                ProposedActual,
                SubmissionType,
                ChangeReason,
                SubmittedBy,
                SubmittedAt,
                ReviewStatus
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                'Pending'
            )
            """,
            (
                project,
                project_code,
                indicator_id,
                int(project_year),
                int(quarter),
                current_target,
                current_actual,
                current_target,
                proposed_actual,
                submission_type,
                change_reason,
                submitted_by,
                submitted_at,
            ),
        )

        submission_id = cursor.lastrowid

        connection.commit()

        return {
            "success": True,
            "submission_id": submission_id,
            "submission_type": submission_type,
        }

    except sqlite3.IntegrityError as error:
        connection.rollback()

        return {
            "success": False,
            "message": (
                "The submission could not be saved. "
                f"Database validation: {error}"
            ),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_recent_submissions(
    project_code,
    indicator_id,
):
    """
    Load recent portal submissions for the selected indicator.
    """
    connection = get_connection()

    try:
        return pd.read_sql_query(
            """
            SELECT
                SubmissionID,
                ProjectYear AS Year,
                Quarter,
                CurrentActual,
                ProposedActual,
                SubmissionType,
                SubmittedBy,
                SubmittedAt,
                ReviewStatus
            FROM itt_quarterly_submission_staging
            WHERE ProjectCode = ?
              AND IndicatorID = ?
            ORDER BY SubmissionID DESC
            LIMIT 10
            """,
            connection,
            params=(
                project_code,
                indicator_id,
            ),
        )

    finally:
        connection.close()
# ==================================================
# PORTAL REVIEW AND APPROVAL
# ==================================================

def load_pending_portal_submissions():
    """
    Load all pending quarterly submissions for portal review.
    """
    connection = get_connection()

    try:
        pending_submissions = pd.read_sql_query(
            """
            SELECT
                s.SubmissionID,
                s.Project,
                s.ProjectCode,
                s.IndicatorID,
                m.IndicatorName,
                COALESCE(
                    m.UnitOfMeasure,
                    m.Unit
                ) AS UnitOfMeasure,
                s.ProjectYear,
                s.Quarter,
                s.CurrentTarget,
                s.CurrentActual,
                s.ProposedTarget,
                s.ProposedActual,
                s.SubmissionType,
                s.ChangeReason,
                s.SubmittedBy,
                s.SubmittedAt,
                s.ReviewStatus
            FROM itt_quarterly_submission_staging AS s
            LEFT JOIN itt_indicator_master AS m
                ON s.IndicatorID = m.IndicatorID
            WHERE s.ReviewStatus = 'Pending'
            ORDER BY
                s.SubmittedAt,
                s.SubmissionID
            """,
            connection,
        )

        return pending_submissions

    except Exception:
        pending_submissions = pd.read_sql_query(
            """
            SELECT
                SubmissionID,
                Project,
                ProjectCode,
                IndicatorID,
                ProjectYear,
                Quarter,
                CurrentTarget,
                CurrentActual,
                ProposedTarget,
                ProposedActual,
                SubmissionType,
                ChangeReason,
                SubmittedBy,
                SubmittedAt,
                ReviewStatus
            FROM itt_quarterly_submission_staging
            WHERE ReviewStatus = 'Pending'
            ORDER BY
                SubmittedAt,
                SubmissionID
            """,
            connection,
        )

        pending_submissions["IndicatorName"] = (
            pending_submissions["IndicatorID"]
        )

        pending_submissions["UnitOfMeasure"] = None

        return pending_submissions

    finally:
        connection.close()


def approve_portal_submission(
    submission_id,
    approved_by,
    approval_comment,
):
    """
    Approve one portal submission.

    The approved value is copied into portal_approved_staging.
    Production and dashboard_data_staging remain unchanged.
    """
    connection = get_connection()

    try:
        submission = connection.execute(
            """
            SELECT *
            FROM itt_quarterly_submission_staging
            WHERE SubmissionID = ?
              AND ReviewStatus = 'Pending'
            LIMIT 1
            """,
            (
                int(submission_id),
            ),
        ).fetchone()

        if submission is None:
            return {
                "success": False,
                "message": (
                    "The selected submission is no longer pending."
                ),
            }

        existing_approval = connection.execute(
            """
            SELECT PortalApprovalID
            FROM portal_approved_staging
            WHERE SubmissionID = ?
            LIMIT 1
            """,
            (
                int(submission_id),
            ),
        ).fetchone()

        if existing_approval is not None:
            return {
                "success": False,
                "message": (
                    "This submission is already in "
                    "portal_approved_staging."
                ),
            }

        approved_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            INSERT INTO portal_approved_staging (
                SubmissionID,
                Project,
                ProjectCode,
                IndicatorID,
                ProjectYear,
                Quarter,
                CurrentTarget,
                CurrentActual,
                ApprovedTarget,
                ApprovedActual,
                SubmissionType,
                SubmittedBy,
                SubmittedAt,
                ApprovedBy,
                ApprovedAt,
                ApprovalComment,
                DatasetInclusionStatus
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?,
                'Pending Dataset Review'
            )
            """,
            (
                submission["SubmissionID"],
                submission["Project"],
                submission["ProjectCode"],
                submission["IndicatorID"],
                submission["ProjectYear"],
                submission["Quarter"],
                submission["CurrentTarget"],
                submission["CurrentActual"],
                submission["ProposedTarget"],
                submission["ProposedActual"],
                submission["SubmissionType"],
                submission["SubmittedBy"],
                submission["SubmittedAt"],
                approved_by,
                approved_at,
                approval_comment,
            ),
        )

        portal_approval_id = cursor.lastrowid

        connection.execute(
            """
            UPDATE itt_quarterly_submission_staging
            SET
                ReviewStatus = 'Approved',
                ReviewedBy = ?,
                ReviewedAt = ?,
                ReviewComment = ?
            WHERE SubmissionID = ?
              AND ReviewStatus = 'Pending'
            """,
            (
                approved_by,
                approved_at,
                approval_comment,
                int(submission_id),
            ),
        )

        connection.commit()

        return {
            "success": True,
            "portal_approval_id": portal_approval_id,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def reject_portal_submission(
    submission_id,
    reviewed_by,
    review_comment,
):
    """
    Reject one pending portal submission.
    """
    connection = get_connection()

    try:
        reviewed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            UPDATE itt_quarterly_submission_staging
            SET
                ReviewStatus = 'Rejected',
                ReviewedBy = ?,
                ReviewedAt = ?,
                ReviewComment = ?
            WHERE SubmissionID = ?
              AND ReviewStatus = 'Pending'
            """,
            (
                reviewed_by,
                reviewed_at,
                review_comment,
                int(submission_id),
            ),
        )

        if cursor.rowcount == 0:
            connection.rollback()

            return {
                "success": False,
                "message": (
                    "The selected submission is no longer pending."
                ),
            }

        connection.commit()

        return {
            "success": True,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def return_portal_submission(
    submission_id,
    reviewed_by,
    review_comment,
):
    """
    Return one submission to the submitter for correction.
    """
    connection = get_connection()

    try:
        reviewed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            UPDATE itt_quarterly_submission_staging
            SET
                ReviewStatus = 'Returned',
                ReviewedBy = ?,
                ReviewedAt = ?,
                ReviewComment = ?
            WHERE SubmissionID = ?
              AND ReviewStatus = 'Pending'
            """,
            (
                reviewed_by,
                reviewed_at,
                review_comment,
                int(submission_id),
            ),
        )

        if cursor.rowcount == 0:
            connection.rollback()

            return {
                "success": False,
                "message": (
                    "The selected submission is no longer pending."
                ),
            }

        connection.commit()

        return {
            "success": True,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_portal_approved_items():
    """
    Load portal-approved items awaiting dataset review.
    """
    connection = get_connection()

    try:
        approved_items = pd.read_sql_query(
            """
            SELECT
                PortalApprovalID,
                SubmissionID,
                Project,
                IndicatorID,
                ProjectYear,
                Quarter,
                CurrentActual,
                ApprovedActual,
                SubmissionType,
                ApprovedBy,
                ApprovedAt,
                DatasetInclusionStatus
            FROM portal_approved_staging
            ORDER BY
                PortalApprovalID DESC
            LIMIT 20
            """,
            connection,
        )

        return approved_items

    finally:
        connection.close()
def resubmit_returned_submission(
    original_submission_id,
    revised_actual,
    resubmission_comment,
    resubmitted_by,
):
    """
    Create a new Pending submission from a Returned submission.

    The original Returned record remains unchanged for audit history.
    """
    connection = get_connection()

    try:
        original_submission = connection.execute(
            """
            SELECT *
            FROM itt_quarterly_submission_staging
            WHERE SubmissionID = ?
              AND ReviewStatus = 'Returned'
            LIMIT 1
            """,
            (
                int(original_submission_id),
            ),
        ).fetchone()

        if original_submission is None:
            return {
                "success": False,
                "message": (
                    "The selected submission is not available "
                    "for resubmission."
                ),
            }

        existing_pending = connection.execute(
            """
            SELECT SubmissionID
            FROM itt_quarterly_submission_staging
            WHERE ProjectCode = ?
              AND IndicatorID = ?
              AND ProjectYear = ?
              AND Quarter = ?
              AND ReviewStatus = 'Pending'
            LIMIT 1
            """,
            (
                original_submission["ProjectCode"],
                original_submission["IndicatorID"],
                original_submission["ProjectYear"],
                original_submission["Quarter"],
            ),
        ).fetchone()

        if existing_pending is not None:
            return {
                "success": False,
                "message": (
                    "A pending submission already exists for "
                    "this indicator and reporting period. "
                    f"Pending Submission ID: "
                    f"{existing_pending['SubmissionID']}."
                ),
            }

        resubmitted_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        original_review_comment = (
            original_submission["ReviewComment"]
        )

        combined_comment_parts = [
            (
                f"Resubmission of returned Submission "
                f"{original_submission_id}."
            )
        ]

        if (
            original_review_comment is not None
            and str(
                original_review_comment
            ).strip()
        ):
            combined_comment_parts.append(
                "Previous reviewer feedback: "
                + str(
                    original_review_comment
                ).strip()
            )

        if resubmission_comment.strip():
            combined_comment_parts.append(
                "Submitter correction note: "
                + resubmission_comment.strip()
            )

        combined_comment = " ".join(
            combined_comment_parts
        )

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            INSERT INTO itt_quarterly_submission_staging (
                Project,
                ProjectCode,
                IndicatorID,
                ProjectYear,
                Quarter,
                CurrentTarget,
                CurrentActual,
                ProposedTarget,
                ProposedActual,
                SubmissionType,
                ChangeReason,
                SubmittedBy,
                SubmittedAt,
                ReviewStatus
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                'Pending'
            )
            """,
            (
                original_submission["Project"],
                original_submission["ProjectCode"],
                original_submission["IndicatorID"],
                original_submission["ProjectYear"],
                original_submission["Quarter"],
                original_submission["CurrentTarget"],
                original_submission["CurrentActual"],
                original_submission["ProposedTarget"],
                float(revised_actual),
                original_submission["SubmissionType"],
                combined_comment,
                resubmitted_by.strip(),
                resubmitted_at,
            ),
        )

        new_submission_id = cursor.lastrowid

        connection.execute(
            """
            UPDATE itt_quarterly_submission_staging
            SET
                ReviewStatus = 'Rejected',
                ReviewComment =
                    COALESCE(
                        ReviewComment,
                        ''
                    ) || ' [Resubmitted]'
            WHERE SubmissionID = ?
              AND ReviewStatus = 'Returned'
            """,
            (
                int(original_submission_id),
            ),
        )

        connection.commit()

        return {
            "success": True,
            "new_submission_id":
                new_submission_id,
        }

        connection.commit()

        return {
            "success": True,
            "new_submission_id": new_submission_id,
        }

    except sqlite3.IntegrityError as error:
        connection.rollback()

        return {
            "success": False,
            "message": (
                "The resubmission could not be saved. "
                f"Database validation: {error}"
            ),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
# ==================================================
# LOAD REPOSITORY
# ==================================================

try:
    indicator_repository = (
        load_indicator_repository()
    )

except Exception as error:
    st.error(
        f"Unable to load the indicator repository: {error}"
    )
    st.stop()


if indicator_repository.empty:
    st.error(
        "The ITT indicator repository is empty."
    )
    st.stop()


# # ==================================================
# PAGE HEADER
# ==================================================

st.title("📝 ITT Data Entry Portal")

st.caption(
    "Report quarterly actuals for approved ITT indicators. "
    "Submitted values remain in staging until reviewed and approved."
)



# ==================================================
# SECTION 1: REPORTING SELECTION
# ==================================================

st.header("1. Reporting Selection")

selection_col1, selection_col2 = st.columns(
    [1, 3]
)

project_options = sorted(
    indicator_repository["Project"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

with selection_col1:
    selected_project = st.selectbox(
        "Project",
        project_options,
        key="itt_entry_project",
    )

project_indicators = indicator_repository[
    indicator_repository["Project"].astype(str)
    == selected_project
].copy()

project_indicators = (
    project_indicators
    .sort_values(
        [
            "IndicatorName",
            "IndicatorID",
        ]
    )
    .drop_duplicates(
        subset=["IndicatorID"],
        keep="first",
    )
)

indicator_label_to_id = {}

for _, repository_row in project_indicators.iterrows():
    indicator_label = (
        f"{repository_row['IndicatorName']} "
        f"({repository_row['IndicatorID']})"
    )

    indicator_label_to_id[
        indicator_label
    ] = repository_row["IndicatorID"]

with selection_col2:
    selected_indicator_label = st.selectbox(
        "Indicator",
        list(
            indicator_label_to_id.keys()
        ),
        key="itt_entry_indicator",
    )

selected_indicator_id = (
    indicator_label_to_id[
        selected_indicator_label
    ]
)

selected_indicator_rows = indicator_repository[
    indicator_repository["IndicatorID"].astype(str)
    == str(selected_indicator_id)
]

if selected_indicator_rows.empty:
    st.error(
        "The selected indicator could not be retrieved."
    )
    st.stop()

indicator_record = (
    selected_indicator_rows
    .iloc[0]
    .to_dict()
)

project_code = str(
    indicator_record.get(
        "ProjectCode",
        "",
    )
).strip()

indicator_name = str(
    indicator_record.get(
        "IndicatorName",
        "",
    )
).strip()

unit_of_measure = get_repository_value(
    indicator_record,
    [
        "UnitOfMeasure",
        "Unit",
    ],
)

baseline = get_repository_value(
    indicator_record,
    [
        "Baseline",
    ],
)

lop_target = get_repository_value(
    indicator_record,
    [
        "ProjectLifeTarget",
        "LoPTarget",
    ],
)

project_duration = get_repository_value(
    indicator_record,
    [
        "LifeProjectYear",
    ],
)

project_duration_numeric = safe_numeric(
    project_duration
)

if project_duration_numeric is None:
    maximum_project_year = 5

else:
    maximum_project_year = min(
        max(
            int(project_duration_numeric),
            1,
        ),
        5,
    )

period_col1, period_col2 = st.columns(2)

with period_col1:
    selected_project_year = st.selectbox(
        "Project Year",
        list(
            range(
                1,
                maximum_project_year + 1,
            )
        ),
        format_func=lambda year: (
            f"Year {year}"
        ),
        key="itt_entry_project_year",
    )

with period_col2:
    selected_quarter = st.selectbox(
        "Reporting Quarter",
        [
            1,
            2,
            3,
            4,
        ],
        format_func=lambda quarter: (
            f"Q{quarter}"
        ),
        key="itt_entry_quarter",
    )

annual_target = get_annual_target(
    indicator_record,
    selected_indicator_id,
    selected_project_year,
)

period_values = get_current_period_values(
    project_code,
    selected_indicator_id,
    selected_project_year,
    selected_quarter,
)

current_quarter_target = period_values[
    "QuarterTarget"
]

current_quarter_actual = period_values[
    "QuarterActual"
]


# ==================================================
# SECTION 2: INDICATOR AND PERIOD SUMMARY
# ==================================================

summary_left, summary_right = st.columns([4,1])

with summary_left:

    st.subheader("Selected Indicator for Update")

    st.markdown(
        f"""
        <div style="
            font-size:14px;
            font-weight:400;
            color:#4B5563;
            line-height:2;
        ">
        {indicator_name}
        </div>
        """,
        unsafe_allow_html=True,
    )


summary_col1, summary_col2, summary_col3, summary_col4 = (
    st.columns(4)
)

with summary_col1:
    st.markdown("**Indicator ID**")
    st.write(selected_indicator_id)

    st.markdown("**Unit of Measure**")
    st.write(
        unit_of_measure
        if unit_of_measure
        else "Not available"
    )

with summary_col2:
    st.markdown("**Baseline**")
    st.write(
        format_value(
            baseline,
            unit_of_measure,
        )
    )

    st.markdown("**Life-of-Project Target**")
    st.write(
        format_value(
            lop_target,
            unit_of_measure,
        )
    )

with summary_col3:
    st.markdown(
        f"**Year {selected_project_year} Target**"
    )

    st.write(
        format_value(
            annual_target,
            unit_of_measure,
        )
    )

    st.markdown(
        f"**Q{selected_quarter} Target**"
    )

    st.write(
        format_value(
            current_quarter_target,
            unit_of_measure,
        )
    )

with summary_col4:
    st.markdown(
        f"**Q{selected_quarter} Approved Actual**"
    )

    st.write(
        format_value(
            current_quarter_actual,
            unit_of_measure,
        )
    )

    st.markdown("**Reporting Status**")

    if current_quarter_actual is None:
        st.write("⚪ Not Reported")

    else:
        st.write("🟢 Approved")


# ==================================================
# SECTION 3: SELECTED PERIOD SUMMARY
# ==================================================

st.header(
    f"3. Selected Period: "
    f"Year {selected_project_year}, Q{selected_quarter}"
)

pending_year_submissions = (
    load_pending_year_submissions(
        project_code,
        selected_indicator_id,
        selected_project_year,
    )
)

selected_pending_submission = pd.DataFrame()

if not pending_year_submissions.empty:
    selected_pending_submission = (
        pending_year_submissions[
            pending_year_submissions["Quarter"]
            == selected_quarter
        ].copy()
    )

pending_actual = None
pending_submission_id = None

if not selected_pending_submission.empty:
    pending_actual = safe_numeric(
        selected_pending_submission.iloc[0][
            "ProposedActual"
        ]
    )

    pending_submission_id = int(
        selected_pending_submission.iloc[0][
            "SubmissionID"
        ]
    )

if pending_actual is not None:
    selected_period_status = "🟡 Pending Review"

elif current_quarter_actual is not None:
    selected_period_status = "🟢 Approved"

elif current_quarter_target is not None:
    selected_period_status = "⚪ Not Reported"

else:
    selected_period_status = "⚪ Target Unavailable"

period_summary_col1, period_summary_col2, period_summary_col3, period_summary_col4 = (
    st.columns(4)
)

with period_summary_col1:
    st.markdown("**Quarter Target**")
    st.write(
        format_value(
            current_quarter_target,
            unit_of_measure,
        )
    )

with period_summary_col2:
    st.markdown("**Approved Actual**")
    st.write(
        format_value(
            current_quarter_actual,
            unit_of_measure,
        )
    )

with period_summary_col3:
    st.markdown("**Pending Actual**")
    st.write(
        format_value(
            pending_actual,
            unit_of_measure,
        )
    )

with period_summary_col4:
    st.markdown("**Reporting Status**")
    st.write(selected_period_status)

if pending_submission_id is not None:
    st.info(
        f"Submission {pending_submission_id} is waiting for review. "
        "The pending value has not replaced the approved production value."
    )


# ==================================================
# SECTION 4: YEAR PROGRESS
# ==================================================

st.header(
    f"4. Year {selected_project_year} Progress"
)

year_progress = build_year_progress(
    project_code,
    selected_indicator_id,
    selected_project_year,
)

year_progress["QuarterNumber"] = (
    year_progress["Quarter"]
    .astype(str)
    .str.replace(
        "Q",
        "",
        regex=False,
    )
    .astype(int)
)

if pending_year_submissions.empty:
    year_progress["Pending Actual"] = None
    year_progress["Pending Submission ID"] = None

else:
    pending_progress = (
        pending_year_submissions[
            [
                "Quarter",
                "ProposedActual",
                "SubmissionID",
            ]
        ]
        .rename(
            columns={
                "ProposedActual": "Pending Actual",
                "SubmissionID": "Pending Submission ID",
            }
        )
    )

    year_progress = year_progress.merge(
        pending_progress,
        left_on="QuarterNumber",
        right_on="Quarter",
        how="left",
        suffixes=(
            "",
            "_Pending",
        ),
    )

    if "Quarter_Pending" in year_progress.columns:
        year_progress = year_progress.drop(
            columns=["Quarter_Pending"]
        )

year_progress["Variance"] = (
    year_progress["Approved Actual"]
    - year_progress["Target"]
)

year_progress["Status"] = year_progress.apply(
    lambda row: (
        "🟡 Pending Review"
        if pd.notna(
            row["Pending Actual"]
        )
        else (
            "🟢 Approved"
            if pd.notna(
                row["Approved Actual"]
            )
            else (
                "⚪ Not Reported"
                if pd.notna(
                    row["Target"]
                )
                else "⚪ Target Unavailable"
            )
        )
    ),
    axis=1,
)

year_progress["Selected"] = (
    year_progress["QuarterNumber"].apply(
        lambda quarter_number: (
            "◀ Selected"
            if quarter_number
            == selected_quarter
            else ""
        )
    )
)

display_progress = year_progress.copy()

display_progress["Target"] = (
    display_progress["Target"].apply(
        lambda value: format_value(
            value,
            unit_of_measure,
        )
    )
)

display_progress["Approved Actual"] = (
    display_progress[
        "Approved Actual"
    ].apply(
        lambda value: format_value(
            value,
            unit_of_measure,
        )
    )
)

display_progress["Pending Actual"] = (
    display_progress[
        "Pending Actual"
    ].apply(
        lambda value: format_value(
            value,
            unit_of_measure,
        )
    )
)

display_progress["Variance"] = (
    year_progress["Variance"].apply(
        lambda value: (
            format_value(
                value,
                unit_of_measure,
            )
            if pd.notna(value)
            else "Not available"
        )
    )
)

display_progress = display_progress[
    [
        "Quarter",
        "Target",
        "Approved Actual",
        "Pending Actual",
        "Variance",
        "Status",
        "Selected",
    ]
]

def highlight_progress_status(row):
    """
    Apply light row colors according to reporting status.
    """
    status_text = str(
        row["Status"]
    )

    if "Pending" in status_text:
        return [
            "background-color: #FFF7D6"
        ] * len(row)

    if "Approved" in status_text:
        return [
            "background-color: #ECFDF3"
        ] * len(row)

    return [
        "background-color: #F8FAFC"
    ] * len(row)


styled_progress = display_progress.style.apply(
    highlight_progress_status,
    axis=1,
)

st.dataframe(
    styled_progress,
    hide_index=True,
    use_container_width=True,
)

# ==================================================
# SECTION 5: SELECTED QUARTER INTERPRETATION
# ==================================================

if (
    current_quarter_target is not None
    and current_quarter_actual is not None
):
    selected_variance = (
        current_quarter_actual
        - current_quarter_target
    )

    if selected_variance > 0:
        st.success(
            f"Year {selected_project_year}, "
            f"Q{selected_quarter}: approved actual is "
            f"{format_value(selected_variance, unit_of_measure)} "
            f"above the quarterly target."
        )

    elif selected_variance < 0:
        st.warning(
            f"Year {selected_project_year}, "
            f"Q{selected_quarter}: approved actual is "
            f"{format_value(abs(selected_variance), unit_of_measure)} "
            f"below the quarterly target."
        )

    else:
        st.success(
            f"Year {selected_project_year}, "
            f"Q{selected_quarter}: approved actual equals "
            f"the quarterly target."
        )

elif current_quarter_target is None:
    st.warning(
        f"No approved target is available for "
        f"Year {selected_project_year}, Q{selected_quarter}. "
        f"Verify the approved ITT planning data before submitting."
    )

else:
    st.info(
        f"Year {selected_project_year}, "
        f"Q{selected_quarter} has an approved target but "
        f"no approved actual has been reported."
    )


# ==================================================
# SECTION 6: QUARTERLY ACTUAL SUBMISSION
# ==================================================

st.header("6. Submit Quarterly Actual")

pending_submission = get_pending_submission(
    project_code,
    selected_indicator_id,
    selected_project_year,
    selected_quarter,
)

if pending_submission is not None:
    st.warning(
        f"A pending submission already exists for "
        f"Year {selected_project_year}, "
        f"Q{selected_quarter}. "
        f"Submission ID: "
        f"{pending_submission['SubmissionID']}."
    )

if current_quarter_actual is None:
    st.info(
        "This reporting period does not have an approved "
        "actual. The submission will be treated as a new "
        "quarterly result."
    )

else:
    st.warning(
        "This reporting period already has an approved "
        "actual. The submission will be treated as an "
        "update and a reason for change is required."
    )

current_col1, current_col2 = st.columns(2)

with current_col1:
    st.markdown(
        "**Current Approved Target**"
    )

    st.write(
        format_value(
            current_quarter_target,
            unit_of_measure,
        )
    )

with current_col2:
    st.markdown(
        "**Current Approved Actual**"
    )

    st.write(
        format_value(
            current_quarter_actual,
            unit_of_measure,
        )
    )

default_actual = 0.0

if current_quarter_actual is not None:
    default_actual = float(
        current_quarter_actual
    )

submission_form_version = (
    st.session_state.submission_form_version
)

with st.form(
    key=(
        f"itt_quarterly_actual_form_"
        f"{submission_form_version}"
    ),
    clear_on_submit=True,
):
    proposed_actual = st.number_input(
        "New Quarterly Actual",
        min_value=0.0,
        value=default_actual,
        step=1.0,
        help=(
            "Enter the result using the indicator's "
            "approved unit of measure."
        ),
    )

    submitted_by = st.text_input(
        "Submitted By",
        placeholder="Enter the submitter's name",
        key=(
            f"quarterly_submitted_by_"
            f"{submission_form_version}"
        ),
    )
    comment_label = "Reporting Comment"

    if current_quarter_actual is not None:
        comment_label = "Reason for Change"
    reporting_comment = st.text_area(
        comment_label,
        placeholder=(
            "A reason is required when revising "
            "an approved quarterly actual."
        ),
        key=(
            f"quarterly_comment_"
            f"{submission_form_version}"
        ),
    )
    confirmed = st.checkbox(
        "I confirm that the reported value has been "
        "checked against the supporting monitoring source.",
        key=(
            f"quarterly_confirmation_"
            f"{submission_form_version}"
        ),
        disabled=not can_enter_data,
    )
 
    
    submit_button = st.form_submit_button(
        "Submit for Review",
        type="primary",
        disabled=(
            not can_enter_data
        ),
    )



if submit_button:

    if not can_enter_data:

        st.error(
            "Only Data Entry users can submit quarterly data."
        )

        st.stop()

    validation_errors = []

    if not confirmed:
        validation_errors.append(
            "Confirm that the reported value "
            "has been checked."
        )

    if (
        current_quarter_actual is not None
        and not reporting_comment.strip()
    ):
        validation_errors.append(
            "A reason for change is required when "
            "updating an approved actual."
        )

    if validation_errors:
        for validation_error in validation_errors:
            st.error(validation_error)

    else:
        result = save_quarterly_submission(
            project=selected_project,
            project_code=project_code,
            indicator_id=selected_indicator_id,
            project_year=selected_project_year,
            quarter=selected_quarter,
            current_target=current_quarter_target,
            current_actual=current_quarter_actual,
            proposed_actual=float(
                proposed_actual
            ),
            change_reason=(
                reporting_comment.strip()
                or None
            ),
            submitted_by=(
                submitted_by.strip()
            ),
        )

        if result["success"]:
            st.success(
                f"Submission "
                f"{result['submission_id']} "
                f"was saved as "
                f"{result['submission_type']} "
                f"and sent to the review queue."
            )

            st.info(
                "Production data has not been changed. "
                "The proposed value will remain in staging "
                "until it is reviewed and approved."
            )

            reset_submission_form()

        else:
            st.error(
                result["message"]
            )


# ==================================================
# SECTION 7: RECENT SUBMISSIONS
# ==================================================

st.header(
    "7. Recent Submissions for This Indicator"
)

recent_submissions = load_recent_submissions(
    project_code,
    selected_indicator_id,
)

if recent_submissions.empty:
    st.info(
        "No portal submissions have been recorded "
        "for this indicator."
    )

else:
    recent_submissions["Quarter"] = (
        recent_submissions[
            "Quarter"
        ].apply(
            lambda quarter: f"Q{quarter}"
        )
    )

    recent_submissions["CurrentActual"] = (
        recent_submissions[
            "CurrentActual"
        ].apply(
            lambda value: format_value(
                value,
                unit_of_measure,
            )
        )
    )

    recent_submissions["ProposedActual"] = (
        recent_submissions[
            "ProposedActual"
        ].apply(
            lambda value: format_value(
                value,
                unit_of_measure,
            )
        )
    )

    recent_submissions = (
        recent_submissions.rename(
            columns={
                "CurrentActual": (
                    "Current Actual"
                ),
                "ProposedActual": (
                    "Proposed Actual"
                ),
                "SubmissionType": (
                    "Submission Type"
                ),
                "SubmittedBy": (
                    "Submitted By"
                ),
                "SubmittedAt": (
                    "Submitted At"
                ),
                "ReviewStatus": (
                    "Review Status"
                ),
            }
        )
    )

    st.dataframe(
        recent_submissions,
        hide_index=True,
        use_container_width=True,
    )
# ==================================================
# SECTION 7B: NEW INDICATOR REVIEW QUEUE
# ==================================================

st.header(
    "Pending New Indicator Registrations"
)

indicator_connection = get_connection()

try:

    pending_indicators = pd.read_sql_query(
        """
        SELECT
            IndicatorSubmissionID,
            Project,
            ProjectCode,
            ProposedIndicatorID,
            IndicatorName,
            UnitOfMeasure,
            Baseline,
            ProjectLifeTarget,
            LifeProjectYear,
            ReviewStatus,
            SubmittedAt
        FROM itt_indicator_submission_staging
        WHERE ReviewStatus = 'Pending'
        ORDER BY
            IndicatorSubmissionID DESC
        """,
        indicator_connection,
    )

finally:

    indicator_connection.close()

if pending_indicators.empty:

    st.info(
        "No pending indicator registrations."
    )

else:

    st.dataframe(
        pending_indicators,
        hide_index=True,
        use_container_width=True,
    )
    selected_indicator_review = st.selectbox(
        "Select Indicator Registration",
        pending_indicators[
            "IndicatorSubmissionID"
        ].tolist(),
        format_func=lambda value:
            f"Registration {value}",
        key="indicator_review_selector",
    )

    review_col1, review_col2 = st.columns(2)

    with review_col1:

        indicator_review_name = st.text_input(
            "Reviewed By",
            key="new_indicator_reviewer",
        )

    with review_col2:

        indicator_review_action = st.selectbox(
            "Decision",
            [
                "Approve",
                "Return",
                "Reject",
            ],
            key="new_indicator_decision",
        )

    indicator_review_comment = st.text_area(
        "Review Comment",
        key="new_indicator_comment",
    )

    review_new_indicator = st.button(
        "Record Indicator Decision",
        type="primary",
        key="record_indicator_review",
    )
    if review_new_indicator:

        if not indicator_review_name.strip():

            st.error(
                "Reviewed By is required."
            )

        else:

            indicator_connection = get_connection()

            try:

                reviewed_at = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                if indicator_review_action == "Approve":

                    indicator_connection.execute(
                        """
                        UPDATE
                            itt_indicator_submission_staging
                        SET
                            ReviewStatus = 'Approved',
                            ReviewedBy = ?,
                            ReviewedAt = ?,
                            ReviewComment = ?
                        WHERE
                            IndicatorSubmissionID = ?
                        """,
                        (
                            indicator_review_name,
                            reviewed_at,
                            indicator_review_comment,
                            selected_indicator_review,
                        ),
                    )

                elif indicator_review_action == "Return":

                    indicator_connection.execute(
                        """
                        UPDATE
                            itt_indicator_submission_staging
                        SET
                            ReviewStatus = 'Returned',
                            ReviewedBy = ?,
                            ReviewedAt = ?,
                            ReviewComment = ?
                        WHERE
                            IndicatorSubmissionID = ?
                        """,
                        (
                            indicator_review_name,
                            reviewed_at,
                            indicator_review_comment,
                            selected_indicator_review,
                        ),
                    )

                else:

                    indicator_connection.execute(
                        """
                        UPDATE
                            itt_indicator_submission_staging
                        SET
                            ReviewStatus = 'Rejected',
                            ReviewedBy = ?,
                            ReviewedAt = ?,
                            ReviewComment = ?
                        WHERE
                            IndicatorSubmissionID = ?
                        """,
                        (
                            indicator_review_name,
                            reviewed_at,
                            indicator_review_comment,
                            selected_indicator_review,
                        ),
                    )

                indicator_connection.commit()

                st.success(
                    f"Registration "
                    f"{selected_indicator_review} "
                    f"recorded as "
                    f"{indicator_review_action}."
                )

                st.cache_data.clear()
                st.rerun()

            finally:

                indicator_connection.close()
# ==================================================
# SECTION 8: PORTAL REVIEW AND APPROVAL
# ==================================================

st.divider()

st.header("8. Portal Review and Approval")

st.caption(
    "Review quarterly portal submissions before they are "
    "included in the final dataset staging process."
)

pending_portal_submissions = (
    load_pending_portal_submissions()
)

if pending_portal_submissions.empty:
    st.success(
        "There are no pending portal submissions."
    )

else:
    queue_col1, queue_col2 = st.columns(2)

    with queue_col1:
        review_project_filter = st.selectbox(
            "Filter Review Queue by Project",
            [
                "All Projects",
            ]
            + sorted(
                pending_portal_submissions[
                    "Project"
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
            key="portal_review_project_filter",
        )

    with queue_col2:
        st.metric(
            "Pending Portal Submissions",
            len(
                pending_portal_submissions
            ),
        )

    filtered_review_queue = (
        pending_portal_submissions.copy()
    )

    if review_project_filter != "All Projects":
        filtered_review_queue = (
            filtered_review_queue[
                filtered_review_queue[
                    "Project"
                ].astype(str)
                == review_project_filter
            ].copy()
        )

    review_display_columns = [
        "SubmissionID",
        "Project",
        "IndicatorID",
        "IndicatorName",
        "ProjectYear",
        "Quarter",
        "CurrentActual",
        "ProposedActual",
        "SubmissionType",
        "SubmittedBy",
        "SubmittedAt",
    ]

    available_review_columns = [
        column_name
        for column_name in review_display_columns
        if column_name
        in filtered_review_queue.columns
    ]

    review_display = filtered_review_queue[
        available_review_columns
    ].copy()

    if "ProjectYear" in review_display.columns:
        review_display["ProjectYear"] = (
            review_display[
                "ProjectYear"
            ].apply(
                lambda year: f"Year {year}"
            )
        )

    if "Quarter" in review_display.columns:
        review_display["Quarter"] = (
            review_display[
                "Quarter"
            ].apply(
                lambda quarter: f"Q{quarter}"
            )
        )

    review_display = review_display.rename(
        columns={
            "SubmissionID": "Submission ID",
            "IndicatorID": "Indicator ID",
            "IndicatorName": "Indicator",
            "ProjectYear": "Project Year",
            "CurrentActual": "Current Actual",
            "ProposedActual": "Proposed Actual",
            "SubmissionType": "Submission Type",
            "SubmittedBy": "Submitted By",
            "SubmittedAt": "Submitted At",
        }
    )

    st.dataframe(
        review_display,
        hide_index=True,
        use_container_width=True,
    )

    submission_options = (
        filtered_review_queue[
            "SubmissionID"
        ]
        .astype(int)
        .tolist()
    )

    if submission_options:
        selected_review_submission_id = (
            st.selectbox(
                "Select Submission to Review",
                submission_options,
                format_func=lambda submission_id: (
                    f"Submission {submission_id}"
                ),
                key="portal_review_submission",
            )
        )

        selected_review_rows = (
            filtered_review_queue[
                filtered_review_queue[
                    "SubmissionID"
                ].astype(int)
                == int(
                    selected_review_submission_id
                )
            ]
        )

        selected_review_record = (
            selected_review_rows
            .iloc[0]
        )

        selected_review_unit = (
            selected_review_record.get(
                "UnitOfMeasure",
                None,
            )
        )

        st.subheader(
            "Selected Submission Review"
        )

        review_summary_col1, review_summary_col2, review_summary_col3, review_summary_col4 = (
            st.columns(4)
        )

        with review_summary_col1:
            st.markdown("**Project**")
            st.write(
                selected_review_record[
                    "Project"
                ]
            )

            st.markdown("**Indicator ID**")
            st.write(
                selected_review_record[
                    "IndicatorID"
                ]
            )

        with review_summary_col2:
            st.markdown(
                "**Reporting Period**"
            )

            st.write(
                f"Year "
                f"{selected_review_record['ProjectYear']}, "
                f"Q{selected_review_record['Quarter']}"
            )

            st.markdown(
                "**Submission Type**"
            )

            st.write(
                selected_review_record[
                    "SubmissionType"
                ]
            )

        with review_summary_col3:
            st.markdown(
                "**Current Approved Actual**"
            )

            st.write(
                format_value(
                    selected_review_record[
                        "CurrentActual"
                    ],
                    selected_review_unit,
                )
            )

            st.markdown(
                "**Proposed Actual**"
            )

            st.write(
                format_value(
                    selected_review_record[
                        "ProposedActual"
                    ],
                    selected_review_unit,
                )
            )

        with review_summary_col4:
            current_review_actual = (
                safe_numeric(
                    selected_review_record[
                        "CurrentActual"
                    ]
                )
            )

            proposed_review_actual = (
                safe_numeric(
                    selected_review_record[
                        "ProposedActual"
                    ]
                )
            )

            proposed_difference = None

            if (
                current_review_actual
                is not None
                and proposed_review_actual
                is not None
            ):
                proposed_difference = (
                    proposed_review_actual
                    - current_review_actual
                )

            st.markdown(
                "**Proposed Difference**"
            )

            st.write(
                format_value(
                    proposed_difference,
                    selected_review_unit,
                )
            )

            st.markdown("**Submitted By**")

            st.write(
                selected_review_record[
                    "SubmittedBy"
                ]
            )

        change_reason = (
            selected_review_record.get(
                "ChangeReason",
                None,
            )
        )

        if (
            change_reason is not None
            and not pd.isna(change_reason)
            and str(change_reason).strip()
        ):
            st.info(
                "Submission comment: "
                + str(change_reason)
            )
            review_form_version = (
    st.session_state.review_form_version
)

    review_form_version = (
        st.session_state.review_form_version
    )

    with st.form(
        key=(
            f"portal_submission_review_form_"
            f"{review_form_version}"
        ),
        clear_on_submit=True,
    ):
        reviewer_name = st.text_input(
            "Reviewed By",
            key=(
                f"portal_reviewer_name_"
                f"{review_form_version}"
            ),
            disabled=not can_review_submission,
        )

        review_comment = st.text_area(
            "Review Comment",
            key=(
                f"portal_review_comment_"
                f"{review_form_version}"
            ),
            disabled=not can_review_submission,
        )

        review_action = st.radio(
            "Review Decision",
            [
                "Approve",
                "Return for Correction",
                "Reject",
            ],
            horizontal=True,
            key=(
                f"portal_review_action_"
                f"{review_form_version}"
            ),
            disabled=not can_review_submission,
        )

        confirm_review = st.checkbox(
            "I confirm that I reviewed the indicator, "
            "reporting period, supporting comment, "
            "and proposed value.",
            key=(
                f"portal_review_confirmation_"
                f"{review_form_version}"
            ),
            disabled=not can_review_submission,
        )

        review_submit_button = (
            st.form_submit_button(
                "Record Review Decision",
                type="primary",
                disabled=(
                    not can_review_submission
                )
            )
        )



        if review_submit_button:

            if not can_review_submission:

                st.error(
                    "Only Reviewers can record review decisions."
                )

                st.stop()

            review_errors = []

            if not confirm_review:
                review_errors.append(
                    "Confirm that the submission "
                    "was reviewed."
                )

            if (
                review_action
                in [
                    "Return for Correction",
                    "Reject",
                ]
                and not review_comment.strip()
            ):
                review_errors.append(
                    "A review comment is required "
                    "when returning or rejecting a submission."
                )

            if review_errors:
                for review_error in review_errors:
                    st.error(review_error)

            else:
                try:
                    if review_action == "Approve":
                        review_result = (
                            approve_portal_submission(
                                submission_id=(
                                    selected_review_submission_id
                                ),
                                approved_by=(
                                    reviewer_name.strip()
                                ),
                                approval_comment=(
                                    review_comment.strip()
                                    or None
                                ),
                            )
                        )

                    elif (
                        review_action
                        == "Return for Correction"
                    ):
                        review_result = (
                            return_portal_submission(
                                submission_id=(
                                    selected_review_submission_id
                                ),
                                reviewed_by=(
                                    reviewer_name.strip()
                                ),
                                review_comment=(
                                    review_comment.strip()
                                ),
                            )
                        )

                    else:
                        review_result = (
                            reject_portal_submission(
                                submission_id=(
                                    selected_review_submission_id
                                ),
                                reviewed_by=(
                                    reviewer_name.strip()
                                ),
                                review_comment=(
                                    review_comment.strip()
                                ),
                            )
                        )
                    if review_result["success"]:

                        st.success(
                            f"Submission "
                            f"{selected_review_submission_id} "
                            f"was recorded as "
                            f"{review_action}."
                        )

                        if review_action == "Approve":

                            st.info(
                                "The approved item was moved to "
                                "portal_approved_staging with status "
                                "'Pending Dataset Review'. "
                                "No production data was changed."
                            )

                        reset_review_form()

                    else:

                        st.error(
                            review_result["message"]
                        )

                except Exception as error:
                    st.error(
                        f"Unable to record the review "
                        f"decision: {error}"
                    )

   
# ==================================================
# SECTION 9: APPROVED ITEMS AWAITING DATASET REVIEW
# ==================================================

st.header(
    "9. Portal-Approved Items Awaiting Dataset Review"
)

approved_portal_items = (
    load_portal_approved_items()
)

if approved_portal_items.empty:
    st.info(
        "No portal-approved items are currently "
        "awaiting dataset review."
    )

else:
    approved_display = (
        approved_portal_items.copy()
    )

    approved_display["ProjectYear"] = (
        approved_display[
            "ProjectYear"
        ].apply(
            lambda year: f"Year {year}"
        )
    )

    approved_display["Quarter"] = (
        approved_display[
            "Quarter"
        ].apply(
            lambda quarter: f"Q{quarter}"
        )
    )

    approved_display = approved_display.rename(
        columns={
            "PortalApprovalID": (
                "Portal Approval ID"
            ),
            "SubmissionID": (
                "Submission ID"
            ),
            "IndicatorID": (
                "Indicator ID"
            ),
            "ProjectYear": (
                "Project Year"
            ),
            "CurrentActual": (
                "Previous Actual"
            ),
            "ApprovedActual": (
                "Portal-Approved Actual"
            ),
            "SubmissionType": (
                "Submission Type"
            ),
            "ApprovedBy": (
                "Approved By"
            ),
            "ApprovedAt": (
                "Approved At"
            ),
            "DatasetInclusionStatus": (
                "Dataset Inclusion Status"
            ),
        }
    )

    st.dataframe(
        approved_display,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "These records have passed portal review but "
        "have not entered production. The records must "
        "still join the final dataset staging workflow "
        "and pass Lifecycle Management promotion."
    )
# ==================================================
# SUBMISSION STATUS SUMMARY
# ==================================================

connection = get_connection()

try:

    status_counts = pd.read_sql_query(
        """
        SELECT
            ReviewStatus,
            COUNT(*) AS Total
        FROM itt_quarterly_submission_staging
        GROUP BY ReviewStatus
        """,
        connection,
    )

finally:
    connection.close()

status_lookup = {
    row["ReviewStatus"]: row["Total"]
    for _, row in status_counts.iterrows()
}

status_col1, status_col2, status_col3, status_col4 = (
    st.columns(4)
)

status_col1.metric(
    "🟡 Pending",
    status_lookup.get(
        "Pending",
        0,
    ),
)

status_col2.metric(
    "🟢 Approved",
    status_lookup.get(
        "Approved",
        0,
    ),
)

status_col3.metric(
    "🟠 Returned",
    status_lookup.get(
        "Returned",
        0,
    ),
)

status_col4.metric(
    "🔴 Rejected",
    status_lookup.get(
        "Rejected",
        0,
    ),
)
   

# ==================================================
# SECTION 10: RETURNED AND REJECTED SUBMISSIONS
# ==================================================

st.header(
    "10. Returned and Rejected Submissions"
)
status_filter = st.selectbox(
    "Filter by Status",
    [
        "All Statuses",
        "Pending",
        "Approved",
        "Returned",
        "Rejected",
    ],
    key="portal_status_filter",
)

connection = get_connection()

try:

    returned_rejected = pd.read_sql_query(
        """
        SELECT
            SubmissionID,
            Project,
            IndicatorID,
            ProjectYear,
            Quarter,
            ProposedActual,
            ReviewStatus,
            ReviewedBy,
            ReviewComment,
            ReviewedAt,
            SubmittedBy,
            SubmittedAt
        FROM itt_quarterly_submission_staging
        ORDER BY SubmissionID DESC
        LIMIT 200
        """,
        connection,
    )

finally:
    connection.close()

if status_filter != "All Statuses":

    returned_rejected = (
        returned_rejected[
            returned_rejected["ReviewStatus"]
            == status_filter
        ]
        .copy()
    )

if returned_rejected.empty:
    st.info(
        "There are no returned or rejected submissions."
    )

else:

    display_history = (
        returned_rejected.copy()
    )

    display_history["ProjectYear"] = (
        display_history["ProjectYear"]
        .apply(
            lambda year: (
                f"Year {year}"
            )
        )
    )

    display_history["Quarter"] = (
        display_history["Quarter"]
        .apply(
            lambda quarter: (
                f"Q{quarter}"
            )
        )
    )

    display_history["ReviewStatus"] = (
        display_history["ReviewStatus"]
        .replace(
            {
                "Returned":
                    "🟠 Returned",
                "Rejected":
                    "🔴 Rejected",
            }
        )
    )

    display_history = display_history.rename(
        columns={
            "SubmissionID":
                "Submission ID",
            "IndicatorID":
                "Indicator ID",
            "ProjectYear":
                "Project Year",
            "ProposedActual":
                "Proposed Actual",
            "ReviewStatus":
                "Status",
            "ReviewedBy":
                "Reviewed By",
            "ReviewComment":
                "Reviewer Comment",
            "ReviewedAt":
                "Reviewed At",
        }
    )

    st.dataframe(
        display_history,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Returned submissions may be corrected and resubmitted. "
        "Rejected submissions are closed and require a new submission."
    )
# --------------------------------------------------
# RESUBMIT RETURNED ITEM
# --------------------------------------------------

returned_only = (
    returned_rejected[
        returned_rejected["ReviewStatus"]
        == "Returned"
    ]
    .copy()
)

if not returned_only.empty:

    returned_only = returned_only[
        ~returned_only["ReviewComment"]
        .fillna("")
        .str.contains(
            r"\[Resubmitted\]",
            regex=True,
        )
    ]

if not returned_only.empty:
    st.subheader(
        "Correct and Resubmit Returned Item"
    )

    returned_submission_options = (
        returned_only["SubmissionID"]
        .astype(int)
        .tolist()
    )

    selected_returned_submission_id = (
        st.selectbox(
            "Select Returned Submission",
            returned_submission_options,
            format_func=lambda submission_id: (
                f"Returned Submission {submission_id}"
            ),
            key="returned_submission_to_resubmit",
        )
    )

    selected_returned_rows = returned_only[
        returned_only["SubmissionID"].astype(int)
        == int(
            selected_returned_submission_id
        )
    ]

    selected_returned_record = (
        selected_returned_rows
        .iloc[0]
    )

    returned_summary_col1, returned_summary_col2, returned_summary_col3 = (
        st.columns(3)
    )

    with returned_summary_col1:
        st.markdown("**Project**")
        st.write(
            selected_returned_record["Project"]
        )

        st.markdown("**Indicator ID**")
        st.write(
            selected_returned_record["IndicatorID"]
        )

    with returned_summary_col2:
        st.markdown("**Reporting Period**")
        st.write(
            f"Year "
            f"{selected_returned_record['ProjectYear']}, "
            f"Q{selected_returned_record['Quarter']}"
        )

        st.markdown("**Previously Proposed Actual**")
        st.write(
            selected_returned_record[
                "ProposedActual"
            ]
        )

    with returned_summary_col3:
        st.markdown("**Reviewer Feedback**")

        reviewer_feedback = (
            selected_returned_record.get(
                "ReviewComment",
                None,
            )
        )

        if (
            reviewer_feedback is None
            or pd.isna(reviewer_feedback)
            or not str(
                reviewer_feedback
            ).strip()
        ):
            st.write(
                "No reviewer feedback was recorded."
            )

        else:
            st.write(
                str(reviewer_feedback)
            )

    previous_proposed_actual = safe_numeric(
        selected_returned_record[
            "ProposedActual"
        ]
    )

    if previous_proposed_actual is None:
        previous_proposed_actual = 0.0

    with st.form(
        key="returned_submission_resubmit_form",
        clear_on_submit=False,
    ):
        revised_actual = st.number_input(
            "Corrected Quarterly Actual",
            min_value=0.0,
            value=float(
                previous_proposed_actual
            ),
            step=1.0,
            help=(
                "Correct the value based on the "
                "reviewer's feedback."
            ),
        )

        resubmission_comment = st.text_area(
            "Correction Note",
            placeholder=(
                "Explain what was corrected in this "
                "resubmission."
            ),
        )

        resubmitted_by = st.text_input(
            "Resubmitted By",
            placeholder=(
                "Enter the submitter's name"
            ),
        )

        confirm_resubmission = st.checkbox(
            "I confirm that the returned submission "
            "has been corrected and checked."
        )

        resubmit_button = (
            st.form_submit_button(
                "Resubmit for Review",
                type="primary",
            )
        )

    if resubmit_button:
        resubmission_errors = []

        if not resubmitted_by.strip():
            resubmission_errors.append(
                "Resubmitted By is required."
            )

        if not resubmission_comment.strip():
            resubmission_errors.append(
                "A correction note is required."
            )

        if not confirm_resubmission:
            resubmission_errors.append(
                "Confirm that the returned submission "
                "was corrected and checked."
            )

        if resubmission_errors:
            for resubmission_error in resubmission_errors:
                st.error(
                    resubmission_error
                )

        else:
            try:
                resubmission_result = (
                    resubmit_returned_submission(
                        original_submission_id=(
                            selected_returned_submission_id
                        ),
                        revised_actual=(
                            revised_actual
                        ),
                        resubmission_comment=(
                            resubmission_comment
                        ),
                        resubmitted_by=(
                            resubmitted_by
                        ),
                    )
                )

                if resubmission_result["success"]:
                    st.success(
                        f"Returned Submission "
                        f"{selected_returned_submission_id} "
                        f"was corrected and resubmitted as "
                        f"new Pending Submission "
                        f"{resubmission_result['new_submission_id']}."
                    )

                if resubmission_result["success"]:

                    st.success(
                        f"Returned Submission "
                        f"{selected_returned_submission_id} "
                        f"was corrected and resubmitted as "
                        f"new Pending Submission "
                        f"{resubmission_result['new_submission_id']}."
                    )

                    st.info(
                        "The original returned item remains "
                        "in the audit trail and the corrected "
                        "submission is now waiting for review."
                    )

                    reset_resubmit_form()

                else:

                    st.error(
                        resubmission_result[
                            "message"
                        ]
                    )
            except Exception as error:

                st.error(
                    f"Unable to resubmit the returned "
                    f"item: {error}"
                )
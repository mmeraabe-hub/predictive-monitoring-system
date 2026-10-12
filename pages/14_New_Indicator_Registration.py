import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="New Indicator Registration",
    page_icon="➕",
    layout="wide",
)

DATABASE_PATH = "predictive_monitoring.db"


# ==================================================
# DATABASE HELPERS
# ==================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_exists(connection, table_name):
    result = connection.execute(
        """
        SELECT COUNT(1)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()[0]
    return result > 0


def get_table_columns(connection, table_name):
    if not table_exists(connection, table_name):
        return []
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()
    return [row["name"] for row in rows]


def add_column_if_missing(
    connection,
    table_name,
    column_name,
    column_definition,
):
    if column_name not in get_table_columns(connection, table_name):
        connection.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )


def prepare_indicator_staging_schema():
    connection = get_connection()
    try:
        if not table_exists(
            connection,
            "itt_indicator_submission_staging",
        ):
            raise RuntimeError(
                "itt_indicator_submission_staging does not exist."
            )

        if not table_exists(
            connection,
            "itt_indicator_target_staging",
        ):
            raise RuntimeError(
                "itt_indicator_target_staging does not exist."
            )

        submission_columns = {
            "SubmittedBy": "TEXT",
            "SubmittedAt": "TEXT",
            "ReviewedBy": "TEXT",
            "ReviewedAt": "TEXT",
            "ReviewComment": "TEXT",
            "DatasetInclusionStatus": "TEXT",
            "DatasetIncludedAt": "TEXT",
            "DatasetIncludedBy": "TEXT",
        }

        for column_name, definition in submission_columns.items():
            add_column_if_missing(
                connection,
                "itt_indicator_submission_staging",
                column_name,
                definition,
            )

        add_column_if_missing(
            connection,
            "itt_indicator_target_staging",
            "QuarterActual",
            "REAL",
        )

        connection.commit()
    finally:
        connection.close()


prepare_indicator_staging_schema()


# ==================================================
# FORM RESET
# ==================================================

if "new_indicator_form_version" not in st.session_state:
    st.session_state.new_indicator_form_version = 0

if "new_indicator_year_data" not in st.session_state:
    st.session_state.new_indicator_year_data = {}


def reset_new_indicator_form():
    st.session_state.new_indicator_form_version += 1
    st.session_state.new_indicator_year_data = {}
    st.cache_data.clear()
    st.rerun()


# ==================================================
# REPOSITORY HELPERS
# ==================================================

@st.cache_data
def load_project_repository():
    connection = get_connection()
    try:
        if not table_exists(connection, "itt_indicator_master"):
            return pd.DataFrame(columns=["Project", "ProjectCode"])

        columns = get_table_columns(
            connection,
            "itt_indicator_master",
        )

        if "Project" not in columns or "ProjectCode" not in columns:
            return pd.DataFrame(columns=["Project", "ProjectCode"])

        return pd.read_sql_query(
            """
            SELECT DISTINCT
                Project,
                ProjectCode
            FROM itt_indicator_master
            WHERE Project IS NOT NULL
              AND TRIM(Project) <> ''
              AND ProjectCode IS NOT NULL
              AND TRIM(ProjectCode) <> ''
            ORDER BY Project
            """,
            connection,
        )
    finally:
        connection.close()


@st.cache_data
def load_result_level_standards():
    connection = get_connection()
    try:
        standards = []
        source_tables = [
            "itt_indicator_master",
            "itt_indicator_submission_staging",
            "dashboard_data",
        ]

        for table_name in source_tables:
            if not table_exists(connection, table_name):
                continue

            columns = get_table_columns(connection, table_name)
            if "ResultLevelStandard" not in columns:
                continue

            rows = connection.execute(
                f"""
                SELECT DISTINCT ResultLevelStandard
                FROM {table_name}
                WHERE ResultLevelStandard IS NOT NULL
                  AND TRIM(ResultLevelStandard) <> ''
                ORDER BY ResultLevelStandard
                """
            ).fetchall()

            standards.extend(
                str(row["ResultLevelStandard"]).strip()
                for row in rows
            )

        return sorted(set(standards))
    finally:
        connection.close()


def generate_next_indicator_id(project_code):
    normalized_code = str(project_code or "").strip().upper()
    if not normalized_code:
        return "Project code required"

    connection = get_connection()
    try:
        existing_ids = []
        sources = [
            (
                "itt_indicator_master",
                "IndicatorID",
            ),
            (
                "itt_indicator_submission_staging",
                "ProposedIndicatorID",
            ),
        ]

        for table_name, id_column in sources:
            if not table_exists(connection, table_name):
                continue

            columns = get_table_columns(connection, table_name)
            if id_column not in columns or "ProjectCode" not in columns:
                continue

            rows = connection.execute(
                f"""
                SELECT {id_column}
                FROM {table_name}
                WHERE UPPER(TRIM(ProjectCode)) = ?
                """,
                (normalized_code,),
            ).fetchall()

            existing_ids.extend(
                row[id_column]
                for row in rows
                if row[id_column]
            )

        highest_number = 0
        for indicator_id in existing_ids:
            try:
                indicator_number = int(
                    str(indicator_id).split("_")[-1]
                )
                highest_number = max(
                    highest_number,
                    indicator_number,
                )
            except (TypeError, ValueError):
                continue

        return f"{normalized_code}_{highest_number + 1:03d}"
    finally:
        connection.close()


# ==================================================
# SAVE AND REVIEW FUNCTIONS
# ==================================================

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
    submitted_by,
):
    connection = get_connection()
    try:
        existing = connection.execute(
            """
            SELECT IndicatorSubmissionID
            FROM itt_indicator_submission_staging
            WHERE ProposedIndicatorID = ?
              AND ReviewStatus = 'Pending'
            LIMIT 1
            """,
            (indicator_id,),
        ).fetchone()

        if existing is not None:
            return {
                "success": False,
                "message": (
                    "A pending registration already exists for "
                    "this Generated Indicator ID."
                ),
            }

        submitted_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")

        cursor = connection.execute(
            """
            INSERT INTO itt_indicator_submission_staging (
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
                SubmittedBy,
                SubmittedAt,
                ReviewStatus
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?,
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
                int(project_duration),
                unit_of_measure,
                float(baseline),
                float(lop_target),
                annual_targets.get(1),
                annual_targets.get(2),
                annual_targets.get(3),
                annual_targets.get(4),
                annual_targets.get(5),
                submitted_by,
                submitted_at,
            ),
        )

        submission_id = cursor.lastrowid

        for year_number, quarter_dictionary in quarter_targets.items():
            for quarter_number, values in quarter_dictionary.items():
                quarter_target = values.get("Target")
                quarter_actual = values.get("Actual")

                if quarter_target is not None:
                    quarter_target = float(quarter_target)
                if quarter_actual is not None:
                    quarter_actual = float(quarter_actual)

                connection.execute(
                    """
                    INSERT INTO itt_indicator_target_staging (
                        IndicatorSubmissionID,
                        ProposedIndicatorID,
                        ProjectCode,
                        ProjectYear,
                        Quarter,
                        QuarterTarget,
                        QuarterActual
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        submission_id,
                        indicator_id,
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
            "submission_id": submission_id,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_indicator_review(
    indicator_submission_id,
    review_action,
    reviewed_by,
    review_comment,
):
    status_map = {
        "Approve": "Approved",
        "Return for Correction": "Returned",
        "Reject": "Rejected",
    }

    if review_action not in status_map:
        return {
            "success": False,
            "message": "Invalid review decision.",
        }

    review_status = status_map[review_action]
    dataset_status = (
        "Pending Dataset Review"
        if review_action == "Approve"
        else None
    )

    connection = get_connection()
    try:
        reviewed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")
        cursor = connection.execute(
            """
            UPDATE itt_indicator_submission_staging
            SET
                ReviewStatus = ?,
                DatasetInclusionStatus = ?,
                DatasetIncludedAt = NULL,
                DatasetIncludedBy = NULL,
                ReviewedBy = ?,
                ReviewedAt = ?,
                ReviewComment = ?
            WHERE IndicatorSubmissionID = ?
              AND ReviewStatus = 'Pending'
            """,
            (
                review_status,
                dataset_status,
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
                    "The selected registration is no longer pending."
                ),
            }

        connection.commit()
        return {
            "success": True,
            "status": review_status,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def resubmit_returned_indicator(
    indicator_submission_id,
    indicator_name,
    result_level_original,
    result_level_standard,
    unit_of_measure,
    baseline,
    lop_target,
    annual_targets,
    target_rows,
    correction_note,
    resubmitted_by,
):
    connection = get_connection()

    try:
        returned_record = connection.execute(
            """
            SELECT
                IndicatorSubmissionID,
                ReviewComment
            FROM itt_indicator_submission_staging
            WHERE IndicatorSubmissionID = ?
              AND ReviewStatus = 'Returned'
            LIMIT 1
            """,
            (int(indicator_submission_id),),
        ).fetchone()

        if returned_record is None:
            return {
                "success": False,
                "message": (
                    "The selected registration is no longer "
                    "available for correction."
                ),
            }

        previous_feedback = str(
            returned_record["ReviewComment"] or ""
        ).strip()

        correction_history = (
            f"Previous reviewer feedback: {previous_feedback}. "
            if previous_feedback
            else ""
        )
        correction_history += (
            "Submitter correction note: "
            + correction_note.strip()
        )

        resubmitted_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("BEGIN")
        cursor = connection.execute(
            """
            UPDATE itt_indicator_submission_staging
            SET
                IndicatorName = ?,
                ResultLevelOriginal = ?,
                ResultLevelStandard = ?,
                UnitOfMeasure = ?,
                Baseline = ?,
                ProjectLifeTarget = ?,
                Year1Target = ?,
                Year2Target = ?,
                Year3Target = ?,
                Year4Target = ?,
                Year5Target = ?,
                SubmittedBy = ?,
                SubmittedAt = ?,
                ReviewStatus = 'Pending',
                DatasetInclusionStatus = NULL,
                DatasetIncludedAt = NULL,
                DatasetIncludedBy = NULL,
                ReviewedBy = NULL,
                ReviewedAt = NULL,
                ReviewComment = ?
            WHERE IndicatorSubmissionID = ?
              AND ReviewStatus = 'Returned'
            """,
            (
                indicator_name.strip(),
                result_level_original.strip() or None,
                result_level_standard.strip(),
                unit_of_measure.strip(),
                float(baseline),
                float(lop_target),
                annual_targets.get(1),
                annual_targets.get(2),
                annual_targets.get(3),
                annual_targets.get(4),
                annual_targets.get(5),
                resubmitted_by.strip(),
                resubmitted_at,
                correction_history,
                int(indicator_submission_id),
            ),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            return {
                "success": False,
                "message": "The returned registration could not be updated.",
            }

        for row in target_rows:
            connection.execute(
                """
                UPDATE itt_indicator_target_staging
                SET
                    QuarterTarget = ?,
                    QuarterActual = ?
                WHERE IndicatorSubmissionID = ?
                  AND ProjectYear = ?
                  AND Quarter = ?
                """,
                (
                    row["QuarterTarget"],
                    row["QuarterActual"],
                    int(indicator_submission_id),
                    int(row["ProjectYear"]),
                    int(row["Quarter"]),
                ),
            )

        connection.commit()
        return {
            "success": True,
            "submission_id": int(indicator_submission_id),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ==================================================
# PAGE HEADER
# ==================================================

st.title("➕ New Indicator Registration")

st.caption(
    "Register a new ITT indicator. The indicator will "
    "be submitted for review and will not enter the "
    "approved repository until reviewed."
)

st.info(
    "New indicators remain outside production until they pass: "
    "Registration → Review → Dataset Approval → "
    "Lifecycle Promotion → Production"
)

form_version = st.session_state.new_indicator_form_version


# ==================================================
# 1. PROJECT INFORMATION
# ==================================================

st.header("1. Project Information")

project_type = st.radio(
    "Project Type",
    [
        "Existing Project",
        "Create New Project",
    ],
    horizontal=True,
    key=f"project_type_selector_{form_version}",
)

project_repository = load_project_repository()

if project_type == "Existing Project":
    if project_repository.empty:
        st.error(
            "No existing projects are available in the approved "
            "indicator repository."
        )
        st.stop()

    project_options = (
        project_repository["Project"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_project = st.selectbox(
        "Project",
        project_options,
        key=f"new_indicator_project_{form_version}",
    )

    project_row = project_repository[
        project_repository["Project"].astype(str)
        == str(selected_project)
    ].iloc[0]

    project_code = str(project_row["ProjectCode"]).strip()
else:
    project_col1, project_col2 = st.columns(2)
    with project_col1:
        selected_project = st.text_input(
            "Project Name",
            key=f"new_project_name_{form_version}",
        )
    with project_col2:
        project_code = st.text_input(
            "Project Code",
            help=(
                "Use a short unique project code, for example CRRP or RA."
            ),
            key=f"new_project_code_{form_version}",
        )

project_code = str(project_code or "").strip().upper()
st.write(f"Project Code: {project_code or 'Not entered'}")

generated_indicator_id = generate_next_indicator_id(project_code)
if project_code:
    st.success(
        f"Generated Indicator ID: {generated_indicator_id}"
    )
else:
    st.warning(
        "Enter or select a Project Code to generate the Indicator ID."
    )


# ==================================================
# 2. INDICATOR DEFINITION
# ==================================================

st.header("2. Indicator Definition")

indicator_name = st.text_input(
    "Indicator Name",
    key=f"new_indicator_name_{form_version}",
)

definition_col1, definition_col2 = st.columns(2)

with definition_col1:
    result_level_original = st.text_input(
        "Result Level Original",
        key=f"result_level_original_{form_version}",
    )

with definition_col2:
    result_level_options = load_result_level_standards()
    if result_level_options:
        result_level_standard = st.selectbox(
            "Result Level Standard",
            result_level_options,
            key=f"result_level_standard_{form_version}",
        )
    else:
        result_level_standard = st.text_input(
            "Result Level Standard",
            key=f"result_level_standard_{form_version}",
        )

unit_of_measure = st.text_input(
    "Unit of Measure",
    placeholder=(
        "Examples: Participants, Hectares, ETB, Percentage"
    ),
    key=f"unit_of_measure_{form_version}",
)

project_duration = st.selectbox(
    "Project Duration (Years)",
    [1, 2, 3, 4, 5],
    key=f"project_duration_{form_version}",
)


# ==================================================
# 3. INDICATOR PLANNING VALUES
# ==================================================

st.header("3. Indicator Planning Values")
planning_col1, planning_col2 = st.columns(2)

with planning_col1:
    baseline = st.number_input(
        "Baseline",
        value=0.0,
        step=1.0,
        key=f"indicator_baseline_{form_version}",
    )

with planning_col2:
    lop_target = st.number_input(
        "LoP Target",
        value=0.0,
        step=1.0,
        key=f"indicator_lop_target_{form_version}",
    )


# ==================================================
# 4. YEAR PLANNING AND HISTORICAL RESULTS
# ==================================================

st.header("4. Year Planning and Historical Results")

st.caption(
    "Select one project year at a time. Enter the annual "
    "target, quarterly targets, and any available historical "
    "actuals. Quarter actuals may remain blank when reporting "
    "has not yet occurred."
)

selected_year = st.selectbox(
    "Select Project Year",
    list(range(1, int(project_duration) + 1)),
    format_func=lambda year: f"Year {year}",
    key=f"new_indicator_selected_year_{form_version}",
)

default_year_values = {
    "AnnualTarget": 0.0,
    "Quarters": {
        1: {"Target": 0.0, "Actual": None},
        2: {"Target": 0.0, "Actual": None},
        3: {"Target": 0.0, "Actual": None},
        4: {"Target": 0.0, "Actual": None},
    },
}

saved_year_values = st.session_state.new_indicator_year_data.get(
    selected_year,
    default_year_values,
)

annual_target_value = st.number_input(
    f"Year {selected_year} Annual Target",
    min_value=0.0,
    value=float(saved_year_values["AnnualTarget"]),
    step=1.0,
    key=(
        f"new_indicator_annual_target_"
        f"{form_version}_{selected_year}"
    ),
)

entry_rows = []
for quarter_number in range(1, 5):
    entry_rows.append(
        {
            "Quarter": f"Q{quarter_number}",
            "Target": saved_year_values[
                "Quarters"
            ][quarter_number]["Target"],
            "Actual": saved_year_values[
                "Quarters"
            ][quarter_number]["Actual"],
        }
    )

year_editor = st.data_editor(
    pd.DataFrame(entry_rows),
    hide_index=True,
    use_container_width=True,
    disabled=["Quarter"],
    column_config={
        "Quarter": st.column_config.TextColumn("Quarter"),
        "Target": st.column_config.NumberColumn(
            "Quarter Target",
            min_value=0.0,
            format="%.2f",
        ),
        "Actual": st.column_config.NumberColumn(
            "Quarter Actual (Optional)",
            min_value=0.0,
            format="%.2f",
        ),
    },
    key=(
        f"new_indicator_year_editor_"
        f"{form_version}_{selected_year}"
    ),
)

save_year_button = st.button(
    f"Save Year {selected_year} Information",
    key=(
        f"save_new_indicator_year_"
        f"{form_version}_{selected_year}"
    ),
)

if save_year_button:
    quarter_values = {}
    for row_index, row in year_editor.iterrows():
        quarter_number = row_index + 1
        actual_value = row["Actual"]
        if pd.isna(actual_value):
            actual_value = None

        quarter_values[quarter_number] = {
            "Target": float(row["Target"]),
            "Actual": (
                float(actual_value)
                if actual_value is not None
                else None
            ),
        }

    st.session_state.new_indicator_year_data[selected_year] = {
        "AnnualTarget": float(annual_target_value),
        "Quarters": quarter_values,
    }

    st.success(
        f"Year {selected_year} information saved."
    )


# ==================================================
# 5. SAVED PROJECT-YEAR INFORMATION
# ==================================================

st.header("5. Saved Project-Year Information")

summary_rows = []
for year_number in range(1, int(project_duration) + 1):
    values = st.session_state.new_indicator_year_data.get(
        year_number
    )

    summary_row = {
        "Project Year": f"Year {year_number}",
        "Annual Target": (
            values["AnnualTarget"] if values else None
        ),
        "Entry Status": (
            "✅ Saved" if values else "⚪ Not Saved"
        ),
    }

    for quarter_number in range(1, 5):
        summary_row[f"Q{quarter_number} Target"] = (
            values["Quarters"][quarter_number]["Target"]
            if values
            else None
        )
        summary_row[f"Q{quarter_number} Actual"] = (
            values["Quarters"][quarter_number]["Actual"]
            if values
            else None
        )

    summary_rows.append(summary_row)

st.dataframe(
    pd.DataFrame(summary_rows),
    hide_index=True,
    use_container_width=True,
)


# ==================================================
# 6. SUBMIT NEW INDICATOR
# ==================================================

st.header("6. Submit New Indicator for Review")

submitted_by = st.text_input(
    "Submitted By",
    key=f"indicator_submitted_by_{form_version}",
)

submit_button = st.button(
    "Submit New Indicator for Review",
    type="primary",
    key=f"submit_new_indicator_{form_version}",
)

if submit_button:
    errors = []

    missing_years = [
        year_number
        for year_number in range(1, int(project_duration) + 1)
        if year_number
        not in st.session_state.new_indicator_year_data
    ]

    if not str(selected_project).strip():
        errors.append("Project Name is required.")
    if not project_code:
        errors.append("Project Code is required.")
    if not indicator_name.strip():
        errors.append("Indicator Name is required.")
    if not str(result_level_standard).strip():
        errors.append("Result Level Standard is required.")
    if not unit_of_measure.strip():
        errors.append("Unit of Measure is required.")
    if not submitted_by.strip():
        errors.append("Submitted By is required.")
    if missing_years:
        errors.append(
            "Complete and save: "
            + ", ".join(
                f"Year {year_number}"
                for year_number in missing_years
            )
        )

    if errors:
        for error_message in errors:
            st.error(error_message)
    else:
        annual_targets = {}
        quarter_targets = {}

        for year_number in range(
            1,
            int(project_duration) + 1,
        ):
            values = st.session_state.new_indicator_year_data[
                year_number
            ]
            annual_targets[year_number] = values[
                "AnnualTarget"
            ]
            quarter_targets[year_number] = values[
                "Quarters"
            ]

        try:
            result = save_new_indicator_submission(
                project=str(selected_project).strip(),
                project_code=project_code,
                indicator_id=generated_indicator_id,
                indicator_name=indicator_name.strip(),
                result_level_original=(
                    result_level_original.strip() or None
                ),
                result_level_standard=(
                    str(result_level_standard).strip()
                ),
                unit_of_measure=unit_of_measure.strip(),
                project_duration=int(project_duration),
                baseline=baseline,
                lop_target=lop_target,
                annual_targets=annual_targets,
                quarter_targets=quarter_targets,
                submitted_by=submitted_by.strip(),
            )

            if result["success"]:
                st.success(
                    "Indicator submitted successfully. "
                    f"Submission ID: {result['submission_id']}."
                )
                st.info(
                    "The indicator is now waiting for review. "
                    "Production data has not been changed."
                )
                reset_new_indicator_form()
            else:
                st.error(result["message"])
        except Exception as error:
            st.error(
                f"Unable to save indicator: {error}"
            )


# ==================================================
# 7. REGISTRATION STATUS
# ==================================================

st.divider()
st.header("7. New Indicator Registration Status")

status_connection = get_connection()
try:
    status_data = pd.read_sql_query(
        """
        SELECT
            IndicatorSubmissionID,
            Project,
            ProjectCode,
            ProposedIndicatorID,
            IndicatorName,
            ResultLevelOriginal,
            ResultLevelStandard,
            UnitOfMeasure,
            LifeProjectYear,
            Baseline,
            ProjectLifeTarget,
            Year1Target,
            Year2Target,
            Year3Target,
            Year4Target,
            Year5Target,
            SubmittedBy,
            SubmittedAt,
            ReviewStatus,
            DatasetInclusionStatus,
            ReviewedBy,
            ReviewedAt,
            ReviewComment
        FROM itt_indicator_submission_staging
        ORDER BY IndicatorSubmissionID DESC
        """,
        status_connection,
    )
finally:
    status_connection.close()

if status_data.empty:
    st.info(
        "No new indicator registrations have been submitted."
    )
else:
    counts = status_data["ReviewStatus"].value_counts().to_dict()
    status_col1, status_col2, status_col3, status_col4 = (
        st.columns(4)
    )
    status_col1.metric(
        "🟡 Pending",
        counts.get("Pending", 0),
    )
    status_col2.metric(
        "🟢 Approved",
        counts.get("Approved", 0),
    )
    status_col3.metric(
        "🟠 Returned",
        counts.get("Returned", 0),
    )
    status_col4.metric(
        "🔴 Rejected",
        counts.get("Rejected", 0),
    )


# ==================================================
# 8. PENDING REGISTRATIONS AND REVIEW
# ==================================================

st.header("8. Pending New Indicator Registrations")

pending_data = (
    status_data[
        status_data["ReviewStatus"] == "Pending"
    ].copy()
    if not status_data.empty
    else pd.DataFrame()
)

if pending_data.empty:
    st.info(
        "There are no pending new indicator registrations."
    )
else:
    pending_display = pending_data[
        [
            "IndicatorSubmissionID",
            "Project",
            "ProjectCode",
            "ProposedIndicatorID",
            "IndicatorName",
            "ResultLevelStandard",
            "UnitOfMeasure",
            "LifeProjectYear",
            "Baseline",
            "ProjectLifeTarget",
            "SubmittedBy",
            "SubmittedAt",
        ]
    ].copy()

    pending_display = pending_display.rename(
        columns={
            "IndicatorSubmissionID": "Registration ID",
            "ProjectCode": "Project Code",
            "ProposedIndicatorID": "Generated Indicator ID",
            "IndicatorName": "Indicator Name",
            "ResultLevelStandard": "Standard Result Level",
            "UnitOfMeasure": "Unit",
            "LifeProjectYear": "Project Years",
            "ProjectLifeTarget": "LoP Target",
            "SubmittedBy": "Submitted By",
            "SubmittedAt": "Submitted At",
        }
    )

    st.dataframe(
        pending_display,
        hide_index=True,
        use_container_width=True,
    )

    selected_registration_id = st.selectbox(
        "Select Registration to Review",
        pending_data["IndicatorSubmissionID"]
        .astype(int)
        .tolist(),
        format_func=lambda value: f"Registration {value}",
        key="indicator_review_selection",
    )

    selected_registration = pending_data[
        pending_data["IndicatorSubmissionID"].astype(int)
        == int(selected_registration_id)
    ].iloc[0]

    st.subheader("Selected Registration Summary")
    summary_col1, summary_col2, summary_col3 = st.columns(3)

    with summary_col1:
        st.markdown("Generated Indicator ID")
        st.write(selected_registration["ProposedIndicatorID"])
        st.markdown("Project")
        st.write(selected_registration["Project"])

    with summary_col2:
        st.markdown("Indicator Name")
        st.write(selected_registration["IndicatorName"])
        st.markdown("Unit of Measure")
        st.write(selected_registration["UnitOfMeasure"])

    with summary_col3:
        st.markdown("Baseline")
        st.write(selected_registration["Baseline"])
        st.markdown("LoP Target")
        st.write(selected_registration["ProjectLifeTarget"])

    prior_feedback = str(
        selected_registration.get(
            "ReviewComment",
            "",
        )
        or ""
    ).strip()

    if prior_feedback:
        st.info(
            "Correction history: "
            + prior_feedback
        )

    preview_connection = get_connection()
    try:
        target_preview = pd.read_sql_query(
            """
            SELECT
                ProjectYear,
                Quarter,
                QuarterTarget,
                QuarterActual
            FROM itt_indicator_target_staging
            WHERE IndicatorSubmissionID = ?
            ORDER BY ProjectYear, Quarter
            """,
            preview_connection,
            params=(int(selected_registration_id),),
        )
    finally:
        preview_connection.close()

    if not target_preview.empty:
        target_preview["ProjectYear"] = target_preview[
            "ProjectYear"
        ].apply(lambda year: f"Year {year}")
        target_preview["Quarter"] = target_preview[
            "Quarter"
        ].apply(lambda quarter: f"Q{quarter}")
        target_preview = target_preview.rename(
            columns={
                "ProjectYear": "Project Year",
                "QuarterTarget": "Quarter Target",
                "QuarterActual": "Quarter Actual",
            }
        )
        st.subheader(
            "Quarter Targets and Historical Actuals"
        )
        st.dataframe(
            target_preview,
            hide_index=True,
            use_container_width=True,
        )

    with st.form(
        key="new_indicator_review_form",
        clear_on_submit=True,
    ):
        reviewed_by = st.text_input("Reviewed By")
        review_comment = st.text_area("Review Comment")
        review_action = st.radio(
            "Review Decision",
            [
                "Approve",
                "Return for Correction",
                "Reject",
            ],
            horizontal=True,
        )
        review_confirmed = st.checkbox(
            "I confirm that I reviewed the indicator "
            "definition, targets, and available actuals."
        )
        review_submit = st.form_submit_button(
            "Record Indicator Decision",
            type="primary",
        )

    if review_submit:
        errors = []
        if not reviewed_by.strip():
            errors.append("Reviewed By is required.")
        if not review_confirmed:
            errors.append(
                "Confirm that the registration was reviewed."
            )
        if (
            review_action
            in ["Return for Correction", "Reject"]
            and not review_comment.strip()
        ):
            errors.append(
                "A review comment is required when returning "
                "or rejecting a registration."
            )

        if errors:
            for error_message in errors:
                st.error(error_message)
        else:
            try:
                result = record_indicator_review(
                    indicator_submission_id=(
                        selected_registration_id
                    ),
                    review_action=review_action,
                    reviewed_by=reviewed_by.strip(),
                    review_comment=(
                        review_comment.strip() or None
                    ),
                )

                if result["success"]:
                    st.success(
                        f"Registration {selected_registration_id} "
                        f"was recorded as {result['status']}."
                    )
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(result["message"])
            except Exception as error:
                st.error(
                    "Unable to record the review decision: "
                    f"{error}"
                )


# ==================================================
# 9. APPROVED REGISTRATIONS
# ==================================================

st.header(
    "9. Approved New Indicators Awaiting Dataset Review"
)

approved_data = (
    status_data[
        (status_data["ReviewStatus"] == "Approved")
        &
        (
            status_data["DatasetInclusionStatus"]
            .fillna("")
            == "Pending Dataset Review"
        )
    ].copy()
    if not status_data.empty
    else pd.DataFrame()
)

if approved_data.empty:
    st.info(
        "There are no approved new indicators "
        "awaiting dataset review."
    )
else:
    approved_display = approved_data[
        [
            "IndicatorSubmissionID",
            "Project",
            "ProjectCode",
            "ProposedIndicatorID",
            "IndicatorName",
            "UnitOfMeasure",
            "ReviewedBy",
            "ReviewedAt",
        ]
    ].copy()

    approved_display["Dataset Review Status"] = (
        approved_data["DatasetInclusionStatus"].values
    )

    approved_display = approved_display.rename(
        columns={
            "IndicatorSubmissionID": "Registration ID",
            "ProjectCode": "Project Code",
            "ProposedIndicatorID": "Generated Indicator ID",
            "IndicatorName": "Indicator Name",
            "UnitOfMeasure": "Unit",
            "ReviewedBy": "Approved By",
            "ReviewedAt": "Approved At",
        }
    )

    st.dataframe(
        approved_display,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "These indicators passed manager review and are now "
        "waiting for dataset approval on the Data Review & "
        "Approval Dashboard."
    )

# ==================================================
# 10. RETURNED AND REJECTED HISTORY
# ==================================================

st.header("10. Returned and Rejected Registrations")

history_filter = st.selectbox(
    "Filter by Status",
    ["All", "Returned", "Rejected"],
    key="indicator_history_filter",
)

history_data = (
    status_data[
        status_data["ReviewStatus"].isin(
            ["Returned", "Rejected"]
        )
    ].copy()
    if not status_data.empty
    else pd.DataFrame()
)

if history_filter != "All" and not history_data.empty:
    history_data = history_data[
        history_data["ReviewStatus"] == history_filter
    ].copy()

if history_data.empty:
    st.info(
        "There are no returned or rejected "
        "indicator registrations."
    )
else:
    history_display = history_data[
        [
            "IndicatorSubmissionID",
            "Project",
            "ProposedIndicatorID",
            "IndicatorName",
            "ReviewStatus",
            "ReviewComment",
            "ReviewedBy",
            "ReviewedAt",
        ]
    ].copy()

    history_display["ReviewStatus"] = history_display[
        "ReviewStatus"
    ].replace(
        {
            "Returned": "🟠 Returned",
            "Rejected": "🔴 Rejected",
        }
    )

    history_display = history_display.rename(
        columns={
            "IndicatorSubmissionID": "Registration ID",
            "ProposedIndicatorID": "Generated Indicator ID",
            "IndicatorName": "Indicator Name",
            "ReviewStatus": "Status",
            "ReviewComment": "Reviewer Comment",
            "ReviewedBy": "Reviewed By",
            "ReviewedAt": "Reviewed At",
        }
    )

    st.dataframe(
        history_display,
        hide_index=True,
        use_container_width=True,
    )


# ==================================================
# 11. CORRECT AND RESUBMIT RETURNED INDICATOR
# ==================================================

st.header(
    "11. Correct and Resubmit Returned Indicator"
)

returned_data = (
    status_data[
        status_data["ReviewStatus"] == "Returned"
    ].copy()
    if not status_data.empty
    else pd.DataFrame()
)

if returned_data.empty:
    st.info(
        "There are no returned indicator registrations "
        "waiting for correction."
    )
else:
    selected_returned_id = st.selectbox(
        "Select Returned Registration",
        returned_data["IndicatorSubmissionID"]
        .astype(int)
        .tolist(),
        format_func=lambda value: f"Registration {value}",
        key="returned_indicator_to_correct",
    )

    selected_returned = returned_data[
        returned_data["IndicatorSubmissionID"].astype(int)
        == int(selected_returned_id)
    ].iloc[0]

    reviewer_feedback = str(
        selected_returned.get("ReviewComment", "") or ""
    ).strip()

    if reviewer_feedback:
        st.warning(
            "Manager correction request: "
            + reviewer_feedback
        )

    correction_col1, correction_col2 = st.columns(2)

    with correction_col1:
        corrected_indicator_name = st.text_input(
            "Indicator Name",
            value=str(selected_returned["IndicatorName"] or ""),
            key="corrected_indicator_name",
        )
        corrected_result_original = st.text_input(
            "Result Level Original",
            value=str(selected_returned["ResultLevelOriginal"] or ""),
            key="corrected_result_original",
        )
        corrected_result_standard = st.text_input(
            "Result Level Standard",
            value=str(selected_returned["ResultLevelStandard"] or ""),
            key="corrected_result_standard",
        )

    with correction_col2:
        corrected_unit = st.text_input(
            "Unit of Measure",
            value=str(selected_returned["UnitOfMeasure"] or ""),
            key="corrected_unit",
        )
        corrected_baseline = st.number_input(
            "Baseline",
            value=float(selected_returned["Baseline"] or 0.0),
            step=1.0,
            key="corrected_baseline",
        )
        corrected_lop_target = st.number_input(
            "LoP Target",
            value=float(selected_returned["ProjectLifeTarget"] or 0.0),
            step=1.0,
            key="corrected_lop_target",
        )

    project_years = max(
        1,
        min(int(selected_returned["LifeProjectYear"] or 1), 5),
    )

    st.subheader("Correct Annual Targets")
    corrected_annual_targets = {}
    annual_columns = st.columns(project_years)

    for year_number in range(1, project_years + 1):
        original_value = selected_returned[
            f"Year{year_number}Target"
        ]
        with annual_columns[year_number - 1]:
            corrected_annual_targets[year_number] = st.number_input(
                f"Year {year_number} Target",
                min_value=0.0,
                value=float(
                    original_value
                    if pd.notna(original_value)
                    else 0.0
                ),
                step=1.0,
                key=(
                    f"corrected_year_target_"
                    f"{selected_returned_id}_{year_number}"
                ),
            )

    correction_connection = get_connection()
    try:
        correction_targets = pd.read_sql_query(
            """
            SELECT
                ProjectYear,
                Quarter,
                QuarterTarget,
                QuarterActual
            FROM itt_indicator_target_staging
            WHERE IndicatorSubmissionID = ?
            ORDER BY ProjectYear, Quarter
            """,
            correction_connection,
            params=(int(selected_returned_id),),
        )
    finally:
        correction_connection.close()

    st.subheader(
        "Correct Quarterly Planning and Historical Results"
    )
    corrected_targets = st.data_editor(
        correction_targets,
        hide_index=True,
        use_container_width=True,
        disabled=["ProjectYear", "Quarter"],
        column_config={
            "ProjectYear": st.column_config.NumberColumn(
                "Project Year",
                format="%d",
            ),
            "Quarter": st.column_config.NumberColumn(
                "Quarter",
                format="%d",
            ),
            "QuarterTarget": st.column_config.NumberColumn(
                "Quarter Target",
                min_value=0.0,
                format="%.2f",
            ),
            "QuarterActual": st.column_config.NumberColumn(
                "Quarter Actual (Optional)",
                min_value=0.0,
                format="%.2f",
            ),
        },
        key=f"returned_indicator_targets_{selected_returned_id}",
    )

    correction_note = st.text_area(
        "Correction Note",
        placeholder=(
            "Explain what was corrected in response to "
            "the manager's comment."
        ),
        key="returned_indicator_correction_note",
    )
    resubmitted_by = st.text_input(
        "Resubmitted By",
        key="returned_indicator_resubmitted_by",
    )
    correction_confirmed = st.checkbox(
        "I confirm that the returned indicator was corrected "
        "and is ready for manager review again.",
        key="returned_indicator_correction_confirmed",
    )
    resubmit_indicator_button = st.button(
        "Resubmit Indicator for Review",
        type="primary",
        key="resubmit_returned_indicator",
    )

    if resubmit_indicator_button:
        correction_errors = []
        if not corrected_indicator_name.strip():
            correction_errors.append("Indicator Name is required.")
        if not corrected_result_standard.strip():
            correction_errors.append(
                "Result Level Standard is required."
            )
        if not corrected_unit.strip():
            correction_errors.append("Unit of Measure is required.")
        if not correction_note.strip():
            correction_errors.append("A correction note is required.")
        if not resubmitted_by.strip():
            correction_errors.append("Resubmitted By is required.")
        if not correction_confirmed:
            correction_errors.append(
                "Confirm that the correction is complete."
            )

        if correction_errors:
            for correction_error in correction_errors:
                st.error(correction_error)
        else:
            corrected_target_rows = []
            for _, target_row in corrected_targets.iterrows():
                corrected_actual = target_row["QuarterActual"]
                if pd.isna(corrected_actual):
                    corrected_actual = None
                else:
                    corrected_actual = float(corrected_actual)

                corrected_target_rows.append(
                    {
                        "ProjectYear": int(target_row["ProjectYear"]),
                        "Quarter": int(target_row["Quarter"]),
                        "QuarterTarget": float(
                            target_row["QuarterTarget"]
                        ),
                        "QuarterActual": corrected_actual,
                    }
                )

            try:
                resubmit_result = resubmit_returned_indicator(
                    indicator_submission_id=selected_returned_id,
                    indicator_name=corrected_indicator_name,
                    result_level_original=corrected_result_original,
                    result_level_standard=corrected_result_standard,
                    unit_of_measure=corrected_unit,
                    baseline=corrected_baseline,
                    lop_target=corrected_lop_target,
                    annual_targets=corrected_annual_targets,
                    target_rows=corrected_target_rows,
                    correction_note=correction_note,
                    resubmitted_by=resubmitted_by,
                )

                if resubmit_result["success"]:
                    st.success(
                        "Registration "
                        f"{resubmit_result['submission_id']} "
                        "was corrected and returned to the "
                        "Pending manager-review queue."
                    )
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(resubmit_result["message"])
            except Exception as error:
                st.exception(error)

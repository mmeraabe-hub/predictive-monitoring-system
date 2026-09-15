import json
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from utils.database_utils import DB_FILE


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Data Review & Approval",
    page_icon="✅",
    layout="wide"
)


st.title(
    "Data Review & Approval Dashboard"
)


st.caption(
    "Review the uploaded ITT exactly as staged, search and "
    "filter records, inspect data-quality issues, and approve "
    "the dataset before ETL."
)


st.info(
    """
    This page displays the original ITT uploaded through
    the Upload Existing ITT page.

    Approval does not automatically run ETL or retrain models.
    It only confirms that the selected staged upload has been
    reviewed and is eligible for the next controlled step.
    """
)


# ==================================================
# DATABASE INITIALIZATION
# ==================================================

def initialize_review_tables():

    conn = sqlite3.connect(DB_FILE)

    try:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            uploaded_itt_staging (
                UploadID INTEGER
                    PRIMARY KEY AUTOINCREMENT,
                UploadTimestamp TEXT,
                FileName TEXT,
                SourceSheet TEXT,
                RowNumber INTEGER,
                RecordJSON TEXT,
                UploadStatus TEXT,
                UploadBatchID TEXT,
                RecordHash TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            itt_upload_batches (
                UploadBatchID TEXT PRIMARY KEY,
                UploadTimestampUTC TEXT NOT NULL,
                FileName TEXT NOT NULL,
                FileHash TEXT NOT NULL,
                SheetCount INTEGER NOT NULL,
                RowCount INTEGER NOT NULL,
                ColumnCountMaximum INTEGER NOT NULL,
                UploadStatus TEXT NOT NULL,
                ReviewNotes TEXT,
                ApprovedTimestampUTC TEXT,
                ApprovedBy TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            dataset_approval_log (
                ApprovalID INTEGER
                    PRIMARY KEY AUTOINCREMENT,
                UploadBatchID TEXT NOT NULL,
                FileName TEXT NOT NULL,
                PreviousStatus TEXT,
                NewStatus TEXT NOT NULL,
                ApprovedTimestampUTC TEXT NOT NULL,
                ApprovedBy TEXT NOT NULL,
                ReviewNotes TEXT,
                ReviewedRows INTEGER,
                QualityIssueRows INTEGER
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_approval_batch
            ON dataset_approval_log (
                UploadBatchID
            )
            """
        )

        conn.commit()

    finally:

        conn.close()


initialize_review_tables()


# ==================================================
# DATA LOADING
# ==================================================

@st.cache_data
def load_upload_batches():

    conn = sqlite3.connect(DB_FILE)

    try:

        batches = pd.read_sql_query(
            """
            SELECT
                UploadBatchID,
                UploadTimestampUTC,
                FileName,
                FileHash,
                SheetCount,
                RowCount,
                ColumnCountMaximum,
                UploadStatus,
                ReviewNotes,
                ApprovedTimestampUTC,
                ApprovedBy
            FROM itt_upload_batches
            ORDER BY UploadTimestampUTC DESC
            """,
            conn
        )

    finally:

        conn.close()

    return batches


@st.cache_data
def load_staged_rows(
    upload_batch_id
):

    conn = sqlite3.connect(DB_FILE)

    try:

        staged_rows = pd.read_sql_query(
            """
            SELECT
                UploadID,
                UploadTimestamp,
                FileName,
                SourceSheet,
                RowNumber,
                RecordJSON,
                UploadStatus,
                UploadBatchID,
                RecordHash
            FROM uploaded_itt_staging
            WHERE UploadBatchID = ?
            ORDER BY
                SourceSheet,
                RowNumber
            """,
            conn,
            params=[
                upload_batch_id
            ]
        )

    finally:

        conn.close()

    return staged_rows


@st.cache_data
def load_approval_history(
    upload_batch_id
):

    conn = sqlite3.connect(DB_FILE)

    try:

        approval_history = pd.read_sql_query(
            """
            SELECT
                ApprovalID,
                UploadBatchID,
                FileName,
                PreviousStatus,
                NewStatus,
                ApprovedTimestampUTC,
                ApprovedBy,
                ReviewNotes,
                ReviewedRows,
                QualityIssueRows
            FROM dataset_approval_log
            WHERE UploadBatchID = ?
            ORDER BY ApprovedTimestampUTC DESC
            """,
            conn,
            params=[
                upload_batch_id
            ]
        )

    finally:

        conn.close()

    return approval_history


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def reconstruct_uploaded_itt(
    staged_rows
):

    reconstructed_records = []

    metadata_records = []

    column_order = []

    for _, staged_row in staged_rows.iterrows():

        try:

            record = json.loads(
                staged_row["RecordJSON"]
            )

        except (
            TypeError,
            json.JSONDecodeError
        ):

            continue

        for column in record.keys():

            if column not in column_order:

                column_order.append(column)

        reconstructed_records.append(
            record
        )

        metadata_records.append(
            {
                "_UploadID":
                    staged_row["UploadID"],

                "_SourceSheet":
                    staged_row["SourceSheet"],

                "_ExcelRowNumber":
                    staged_row["RowNumber"],

                "_RecordHash":
                    staged_row["RecordHash"]
            }
        )

    if not reconstructed_records:

        return pd.DataFrame()

    reconstructed_data = pd.DataFrame(
        reconstructed_records
    )

    reconstructed_data = (
        reconstructed_data.reindex(
            columns=column_order
        )
    )

    metadata_data = pd.DataFrame(
        metadata_records
    )

    reconstructed_data = pd.concat(
        [
            metadata_data.reset_index(
                drop=True
            ),
            reconstructed_data.reset_index(
                drop=True
            )
        ],
        axis=1
    )

    return reconstructed_data


def normalized_text_series(
    data,
    column
):

    if column not in data.columns:

        return pd.Series(
            "",
            index=data.index,
            dtype="object"
        )

    return (
        data[column]
        .fillna("")
        .astype(str)
        .str.strip()
    )


def count_missing(
    data,
    column
):

    if column not in data.columns:

        return len(data)

    values = normalized_text_series(
        data,
        column
    )

    return int(
        values.eq("").sum()
    )


def create_quality_review(
    uploaded_data
):

    quality_data = uploaded_data.copy()

    indicator_id = normalized_text_series(
        quality_data,
        "IndicatorID"
    )

    project = normalized_text_series(
        quality_data,
        "Project"
    )

    indicators = normalized_text_series(
        quality_data,
        "Indicators"
    )

    unit = normalized_text_series(
        quality_data,
        "Unit of Measure"
    )

    project_code = normalized_text_series(
        quality_data,
        "ProjectCode"
    )

    result_level = normalized_text_series(
        quality_data,
        "ResultLevelStandard"
    ).str.lower()

    project_life_target = (
        pd.to_numeric(
            quality_data.get(
                "Project Life Target",
                pd.Series(
                    index=quality_data.index,
                    dtype="float64"
                )
            ),
            errors="coerce"
        )
    )

    baseline = (
        pd.to_numeric(
            quality_data.get(
                "Baseline",
                pd.Series(
                    index=quality_data.index,
                    dtype="float64"
                )
            ),
            errors="coerce"
        )
    )

    target_columns = [
        column
        for column in quality_data.columns
        if (
            "target" in str(column).lower()
            and not str(column).startswith("_")
        )
    ]

    actual_columns = [
        column
        for column in quality_data.columns
        if (
            "actual" in str(column).lower()
            and not str(column).startswith("_")
        )
    ]

    numeric_review_columns = (
        target_columns
        + actual_columns
    )

    numeric_review_data = pd.DataFrame(
        index=quality_data.index
    )

    for column in numeric_review_columns:

        numeric_review_data[column] = (
            pd.to_numeric(
                quality_data[column],
                errors="coerce"
            )
        )

    if numeric_review_data.empty:

        negative_value_flag = pd.Series(
            False,
            index=quality_data.index
        )

    else:

        negative_value_flag = (
            numeric_review_data.lt(0)
            .any(axis=1)
        )

    duplicate_indicator_flag = (
        indicator_id.ne("")
        & indicator_id.duplicated(
            keep=False
        )
    )

    structural_row_flag = (
        unit.eq("")
        & project_life_target.isna()
        & baseline.isna()
        & result_level.isin(
            [
                "impact",
                "outcome",
                "output"
            ]
        )
    )

    missing_unit_flag = (
        unit.eq("")
        & ~structural_row_flag
    )

    missing_lop_target_flag = (
        project_life_target.isna()
        & ~structural_row_flag
    )

    empty_record_flag = (
        project.eq("")
        & indicators.eq("")
        & indicator_id.eq("")
    )

    quality_data[
        "_Issue_MissingIndicatorID"
    ] = indicator_id.eq("")

    quality_data[
        "_Issue_MissingProject"
    ] = project.eq("")

    quality_data[
        "_Issue_MissingIndicatorText"
    ] = indicators.eq("")

    quality_data[
        "_Issue_MissingProjectCode"
    ] = project_code.eq("")

    quality_data[
        "_Issue_MissingUnit"
    ] = missing_unit_flag

    quality_data[
        "_Issue_MissingLoPTarget"
    ] = missing_lop_target_flag

    quality_data[
        "_Issue_DuplicateIndicatorID"
    ] = duplicate_indicator_flag

    quality_data[
        "_Issue_NegativeValue"
    ] = negative_value_flag

    quality_data[
        "_Issue_EmptyRecord"
    ] = empty_record_flag

    quality_data[
        "_StructuralResultRow"
    ] = structural_row_flag

    issue_columns = [
        column
        for column in quality_data.columns
        if column.startswith(
            "_Issue_"
        )
    ]

    quality_data[
        "_QualityIssueCount"
    ] = (
        quality_data[
            issue_columns
        ]
        .fillna(False)
        .astype(bool)
        .sum(axis=1)
    )

    quality_data[
        "_QualityStatus"
    ] = quality_data[
        "_QualityIssueCount"
    ].apply(
        lambda issue_count:
        "Review Required"
        if issue_count > 0
        else "No Flag"
    )

    return quality_data


def update_batch_approval(
    upload_batch_id,
    file_name,
    previous_status,
    approved_by,
    review_notes,
    reviewed_rows,
    issue_rows
):

    approval_timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = sqlite3.connect(DB_FILE)

    try:

        conn.execute(
            "BEGIN"
        )

        conn.execute(
            """
            UPDATE itt_upload_batches
            SET
                UploadStatus = ?,
                ReviewNotes = ?,
                ApprovedTimestampUTC = ?,
                ApprovedBy = ?
            WHERE UploadBatchID = ?
            """,
            (
                "Approved",
                review_notes,
                approval_timestamp,
                approved_by,
                upload_batch_id
            )
        )

        conn.execute(
            """
            UPDATE uploaded_itt_staging
            SET UploadStatus = ?
            WHERE UploadBatchID = ?
            """,
            (
                "Approved",
                upload_batch_id
            )
        )

        conn.execute(
            """
            INSERT INTO dataset_approval_log (
                UploadBatchID,
                FileName,
                PreviousStatus,
                NewStatus,
                ApprovedTimestampUTC,
                ApprovedBy,
                ReviewNotes,
                ReviewedRows,
                QualityIssueRows
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                upload_batch_id,
                file_name,
                previous_status,
                "Approved",
                approval_timestamp,
                approved_by,
                review_notes,
                int(reviewed_rows),
                int(issue_rows)
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# ==================================================
# LOAD UPLOAD BATCHES
# ==================================================

try:

    batches = load_upload_batches()

except Exception as error:

    st.error(
        "The staged upload batches could not be loaded."
    )

    st.exception(error)

    st.stop()


if batches.empty:

    st.warning(
        "No staged ITT uploads are available."
    )

    st.info(
        "Open Upload Existing ITT, upload a workbook, "
        "confirm it, and save it to staging first."
    )

    st.stop()


# ==================================================
# BATCH SELECTOR
# ==================================================

st.sidebar.header(
    "ITT Review Controls"
)


batch_labels = {}


for _, batch_row in batches.iterrows():

    label = (
        f"{batch_row['FileName']} | "
        f"{batch_row['UploadTimestampUTC']} | "
        f"{batch_row['UploadStatus']} | "
        f"{str(batch_row['UploadBatchID'])[:8]}"
    )

    batch_labels[label] = (
        batch_row["UploadBatchID"]
    )


selected_batch_label = st.sidebar.selectbox(
    "Select Uploaded ITT",
    options=list(
        batch_labels.keys()
    )
)


selected_batch_id = batch_labels[
    selected_batch_label
]


selected_batch = (
    batches[
        batches["UploadBatchID"]
        .eq(selected_batch_id)
    ]
    .iloc[0]
)


# ==================================================
# BATCH SUMMARY
# ==================================================

st.subheader(
    "Selected Upload Summary"
)


summary1, summary2, summary3 = st.columns(3)


summary1.metric(
    "File Name",
    str(
        selected_batch[
            "FileName"
        ]
    )
)


summary2.metric(
    "Rows Uploaded",
    f"{int(selected_batch['RowCount']):,}"
)


summary3.metric(
    "Maximum Columns",
    int(
        selected_batch[
            "ColumnCountMaximum"
        ]
    )
)


summary4, summary5, summary6 = st.columns(3)


summary4.metric(
    "Sheets",
    int(
        selected_batch[
            "SheetCount"
        ]
    )
)


summary5.metric(
    "Upload Status",
    str(
        selected_batch[
            "UploadStatus"
        ]
    )
)


summary6.metric(
    "Uploaded UTC",
    str(
        selected_batch[
            "UploadTimestampUTC"
        ]
    )
)


if (
    str(
        selected_batch[
            "UploadStatus"
        ]
    )
    == "Approved"
):

    st.success(
        "This uploaded ITT has been approved."
    )

else:

    st.warning(
        "This uploaded ITT is pending review."
    )


# ==================================================
# LOAD AND RECONSTRUCT SELECTED ITT
# ==================================================

try:

    staged_rows = load_staged_rows(
        selected_batch_id
    )

except Exception as error:

    st.error(
        "The selected staged ITT could not be loaded."
    )

    st.exception(error)

    st.stop()


if staged_rows.empty:

    st.warning(
        "The selected upload batch contains no staged rows."
    )

    st.stop()


uploaded_itt = reconstruct_uploaded_itt(
    staged_rows
)


if uploaded_itt.empty:

    st.error(
        "The uploaded ITT could not be reconstructed "
        "from the staged JSON records."
    )

    st.stop()


quality_itt = create_quality_review(
    uploaded_itt
)


# ==================================================
# QUALITY SUMMARY
# ==================================================

st.divider()


st.subheader(
    "Data Quality Summary"
)


missing_indicator_ids = int(
    quality_itt[
        "_Issue_MissingIndicatorID"
    ].sum()
)


duplicate_indicator_ids = int(
    quality_itt[
        "_Issue_DuplicateIndicatorID"
    ].sum()
)


missing_units = int(
    quality_itt[
        "_Issue_MissingUnit"
    ].sum()
)


negative_values = int(
    quality_itt[
        "_Issue_NegativeValue"
    ].sum()
)


missing_lop_targets = int(
    quality_itt[
        "_Issue_MissingLoPTarget"
    ].sum()
)


issue_rows = int(
    quality_itt[
        "_QualityIssueCount"
    ].gt(0).sum()
)


quality1, quality2, quality3 = st.columns(3)


quality1.metric(
    "Rows Requiring Review",
    f"{issue_rows:,}"
)


quality2.metric(
    "Missing Indicator Codes",
    f"{missing_indicator_ids:,}"
)


quality3.metric(
    "Duplicate Indicator Codes",
    f"{duplicate_indicator_ids:,}"
)


quality4, quality5, quality6 = st.columns(3)


quality4.metric(
    "Missing Units",
    f"{missing_units:,}"
)


quality5.metric(
    "Missing LoP Targets",
    f"{missing_lop_targets:,}"
)


quality6.metric(
    "Rows with Negative Values",
    f"{negative_values:,}"
)


st.caption(
    "Result-framework structure rows may legitimately "
    "lack units, baselines, or targets. The quality rules "
    "attempt to distinguish these structure rows from "
    "measurable indicator and activity rows."
)


# ==================================================
# SEARCH AND FILTERS
# ==================================================

st.divider()


st.subheader(
    "Search and Filter Uploaded ITT"
)


global_search = st.text_input(
    "Search anything",
    placeholder=(
        "Search indicator description, IndicatorID, "
        "project name, or project code"
    )
)


filter1, filter2 = st.columns(2)


with filter1:

    if "Project" in quality_itt.columns:

        project_options = (
            quality_itt["Project"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        project_options = sorted(
            value
            for value in (
                project_options.unique()
            )
            if value
        )

    else:

        project_options = []


    selected_projects = st.multiselect(
        "Project",
        options=project_options,
        default=[]
    )


with filter2:

    if (
        "ResultLevelStandard"
        in quality_itt.columns
    ):

        result_level_options = (
            quality_itt[
                "ResultLevelStandard"
            ]
            .dropna()
            .astype(str)
            .str.strip()
        )

        result_level_options = sorted(
            value
            for value in (
                result_level_options.unique()
            )
            if value
        )

    else:

        result_level_options = []


    selected_result_levels = (
        st.multiselect(
            "Result Level",
            options=result_level_options,
            default=[]
        )
    )


filter3, filter4 = st.columns(2)


with filter3:

    if "ProjectCode" in quality_itt.columns:

        project_code_options = (
            quality_itt["ProjectCode"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        project_code_options = sorted(
            value
            for value in (
                project_code_options.unique()
            )
            if value
        )

    else:

        project_code_options = []


    selected_project_codes = (
        st.multiselect(
            "Project Code",
            options=project_code_options,
            default=[]
        )
    )


with filter4:

    if "IndicatorID" in quality_itt.columns:

        indicator_code_options = (
            quality_itt["IndicatorID"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        indicator_code_options = sorted(
            value
            for value in (
                indicator_code_options.unique()
            )
            if value
        )

    else:

        indicator_code_options = []


    selected_indicator_codes = (
        st.multiselect(
            "Indicator Code",
            options=indicator_code_options,
            default=[]
        )
    )


show_issues_only = st.toggle(
    "Show rows requiring review only",
    value=False
)


include_structure_rows = st.toggle(
    "Include results-framework structure rows",
    value=True
)


# ==================================================
# APPLY SEARCH AND FILTERS
# ==================================================

filtered_itt = quality_itt.copy()


if global_search.strip():

    search_value = (
        global_search
        .strip()
        .lower()
    )

    searchable_columns = [
        column
        for column in [
            "Project",
            "Indicators",
            "IndicatorID",
            "ProjectCode",
            "ResultLevelOriginal",
            "ResultLevelStandard",
            "Unit of Measure"
        ]
        if column in filtered_itt.columns
    ]

    if searchable_columns:

        search_matches = pd.Series(
            False,
            index=filtered_itt.index
        )

        for column in searchable_columns:

            search_matches = (
                search_matches
                | filtered_itt[column]
                .fillna("")
                .astype(str)
                .str.lower()
                .str.contains(
                    search_value,
                    regex=False
                )
            )

        filtered_itt = filtered_itt[
            search_matches
        ]


if (
    selected_projects
    and "Project" in filtered_itt.columns
):

    filtered_itt = filtered_itt[
        filtered_itt["Project"]
        .astype(str)
        .isin(selected_projects)
    ]


if (
    selected_result_levels
    and "ResultLevelStandard"
    in filtered_itt.columns
):

    filtered_itt = filtered_itt[
        filtered_itt[
            "ResultLevelStandard"
        ]
        .astype(str)
        .isin(
            selected_result_levels
        )
    ]


if (
    selected_project_codes
    and "ProjectCode"
    in filtered_itt.columns
):

    filtered_itt = filtered_itt[
        filtered_itt["ProjectCode"]
        .astype(str)
        .isin(
            selected_project_codes
        )
    ]


if (
    selected_indicator_codes
    and "IndicatorID"
    in filtered_itt.columns
):

    filtered_itt = filtered_itt[
        filtered_itt["IndicatorID"]
        .astype(str)
        .isin(
            selected_indicator_codes
        )
    ]


if show_issues_only:

    filtered_itt = filtered_itt[
        filtered_itt[
            "_QualityIssueCount"
        ].gt(0)
    ]


if not include_structure_rows:

    filtered_itt = filtered_itt[
        ~filtered_itt[
            "_StructuralResultRow"
        ]
    ]


# ==================================================
# DISPLAY RECONSTRUCTED ITT
# ==================================================

st.divider()


st.subheader(
    "Uploaded ITT Preview"
)


st.write(
    f"Displaying **{len(filtered_itt):,}** "
    f"of **{len(quality_itt):,}** staged rows."
)


quality_display_columns = [
    "_QualityStatus",
    "_QualityIssueCount"
]


metadata_display_columns = [
    "_SourceSheet",
    "_ExcelRowNumber"
]


original_columns = [
    column
    for column in uploaded_itt.columns
    if (
        not column.startswith("_")
    )
]


display_columns = (
    quality_display_columns
    + metadata_display_columns
    + original_columns
)


display_columns = [
    column
    for column in display_columns
    if column in filtered_itt.columns
]


st.dataframe(
    filtered_itt[
        display_columns
    ],
    hide_index=True,
    use_container_width=True,
    height=650,
    column_config={
        "_QualityStatus":
            st.column_config.TextColumn(
                "Quality Status"
            ),

        "_QualityIssueCount":
            st.column_config.NumberColumn(
                "Issue Count",
                format="%d"
            ),

        "_SourceSheet":
            st.column_config.TextColumn(
                "Source Sheet"
            ),

        "_ExcelRowNumber":
            st.column_config.NumberColumn(
                "Excel Row",
                format="%d"
            )
    }
)


csv_export = filtered_itt[
    original_columns
].to_csv(
    index=False
).encode(
    "utf-8-sig"
)


st.download_button(
    "Download Filtered ITT Review as CSV",
    data=csv_export,
    file_name=(
        f"{selected_batch['FileName']}"
        "_review.csv"
    ),
    mime="text/csv",
    key="download_filtered_itt"
)


# ==================================================
# APPROVAL WORKFLOW
# ==================================================

st.divider()


st.subheader(
    "Dataset Approval"
)


current_status = str(
    selected_batch[
        "UploadStatus"
    ]
)


if current_status == "Approved":

    st.success(
        "This uploaded ITT has already been approved."
    )

    st.write(
        "Approved by:",
        selected_batch[
            "ApprovedBy"
        ]
    )

    st.write(
        "Approved UTC:",
        selected_batch[
            "ApprovedTimestampUTC"
        ]
    )

    if pd.notna(
        selected_batch[
            "ReviewNotes"
        ]
    ):

        st.write(
            "Review notes:",
            selected_batch[
                "ReviewNotes"
            ]
        )


else:

    if issue_rows > 0:

        st.warning(
            f"""
            This upload contains **{issue_rows:,} rows**
            with one or more automated quality flags.

            Automated flags do not always mean the row is
            invalid. For example, results-framework structure
            rows may legitimately have no unit or target.

            Review the flagged records before approval.
            """
        )

    approved_by = st.text_input(
        "Reviewer name",
        placeholder=(
            "Enter the name of the person "
            "approving this uploaded ITT"
        )
    )


    review_notes = st.text_area(
        "Review notes",
        placeholder=(
            "Describe the review completed, exceptions "
            "accepted, or corrections still required."
        )
    )


    review_confirmation = st.checkbox(
        "I confirm that I reviewed this uploaded ITT "
        "and understand that approval makes it eligible "
        "for the controlled ETL step."
    )


    unresolved_issue_confirmation = False


    if issue_rows > 0:

        unresolved_issue_confirmation = (
            st.checkbox(
                "I reviewed the automated quality flags "
                "and accept the remaining flagged records "
                "for approval."
            )
        )

    else:

        unresolved_issue_confirmation = True


    approval_disabled = not (
        approved_by.strip()
        and review_confirmation
        and unresolved_issue_confirmation
    )


    approve_button = st.button(
        "Approve Selected Dataset",
        type="primary",
        disabled=approval_disabled,
        key="approve_selected_batch"
    )


    if approve_button:

        try:

            update_batch_approval(
                upload_batch_id=(
                    selected_batch_id
                ),
                file_name=str(
                    selected_batch[
                        "FileName"
                    ]
                ),
                previous_status=(
                    current_status
                ),
                approved_by=(
                    approved_by.strip()
                ),
                review_notes=(
                    review_notes.strip()
                ),
                reviewed_rows=len(
                    quality_itt
                ),
                issue_rows=issue_rows
            )


            st.cache_data.clear()


            st.success(
                "✅ The selected ITT upload was approved."
            )


            st.info(
                "Approval is complete. ETL has not yet "
                "run automatically."
            )


            st.rerun()


        except Exception as error:

            st.error(
                "The dataset approval could not be saved."
            )

            st.exception(error)


# ==================================================
# APPROVAL HISTORY
# ==================================================

st.divider()


st.subheader(
    "Approval History"
)


approval_history = (
    load_approval_history(
        selected_batch_id
    )
)


if approval_history.empty:

    st.info(
        "No approval history exists for this upload."
    )

else:

    st.dataframe(
        approval_history,
        hide_index=True,
        use_container_width=True
    )


st.caption(
    "This Version 1 dashboard supports reconstruction, "
    "search, filtering, automated quality review, export, "
    "and approval. Record-level editing and ETL execution "
    "will be added as controlled follow-on capabilities."
)             

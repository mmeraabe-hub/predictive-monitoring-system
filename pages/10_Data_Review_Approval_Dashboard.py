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
# EDITING AND AUDIT-LOG FOUNDATION
# ==================================================

def initialize_editing_tables():

    conn = sqlite3.connect(DB_FILE)

    try:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
            data_change_log (
                ChangeID INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                ChangeTimestampUTC TEXT
                    NOT NULL,

                UploadBatchID TEXT
                    NOT NULL,

                UploadID INTEGER
                    NOT NULL,

                FileName TEXT
                    NOT NULL,

                SourceSheet TEXT,

                ExcelRowNumber INTEGER,

                IndicatorID TEXT,

                FieldName TEXT
                    NOT NULL,

                OldValue TEXT,

                NewValue TEXT,

                ChangedBy TEXT
                    NOT NULL,

                ChangeReason TEXT,

                PreviousRecordHash TEXT,

                NewRecordHash TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_change_log_batch
            ON data_change_log (
                UploadBatchID
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_change_log_record
            ON data_change_log (
                UploadID
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_change_log_indicator
            ON data_change_log (
                IndicatorID
            )
            """
        )

        conn.commit()

    finally:

        conn.close()


initialize_editing_tables()


def values_are_equal(
    old_value,
    new_value
):

    old_missing = (
        old_value is None
        or (
            isinstance(
                old_value,
                float
            )
            and pd.isna(
                old_value
            )
        )
    )

    new_missing = (
        new_value is None
        or (
            isinstance(
                new_value,
                float
            )
            and pd.isna(
                new_value
            )
        )
    )

    if old_missing and new_missing:

        return True

    if old_missing != new_missing:

        return False

    try:

        old_numeric = pd.to_numeric(
            pd.Series(
                [
                    old_value
                ]
            ),
            errors="coerce"
        ).iloc[0]

        new_numeric = pd.to_numeric(
            pd.Series(
                [
                    new_value
                ]
            ),
            errors="coerce"
        ).iloc[0]

        if (
            pd.notna(
                old_numeric
            )
            and pd.notna(
                new_numeric
            )
        ):

            return bool(
                abs(
                    float(old_numeric)
                    - float(new_numeric)
                )
                < 1e-12
            )

    except Exception:

        pass

    return (
        str(old_value).strip()
        == str(new_value).strip()
    )


def normalize_edited_value(
    new_value,
    old_value
):

    try:

        if pd.isna(
            new_value
        ):

            return None

    except TypeError:

        pass

    if isinstance(
        old_value,
        bool
    ):

        if isinstance(
            new_value,
            str
        ):

            return (
                new_value.strip().lower()
                in [
                    "true",
                    "yes",
                    "1"
                ]
            )

        return bool(
            new_value
        )

    if isinstance(
        old_value,
        int
    ) and not isinstance(
        old_value,
        bool
    ):

        try:

            return int(
                float(
                    new_value
                )
            )

        except (
            TypeError,
            ValueError
        ):

            return new_value

    if isinstance(
        old_value,
        float
    ):

        try:

            return float(
                new_value
            )

        except (
            TypeError,
            ValueError
        ):

            return new_value

    return new_value


def create_staged_record_hash(
    source_sheet,
    excel_row_number,
    record_json
):

    import hashlib

    hash_input = (
        f"{source_sheet}|"
        f"{excel_row_number}|"
        f"{record_json}"
    )

    return hashlib.sha256(
        hash_input.encode(
            "utf-8"
        )
    ).hexdigest()


@st.cache_data
def load_change_history(
    upload_batch_id
):

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        change_history = (
            pd.read_sql_query(
                """
                SELECT
                    ChangeID,
                    ChangeTimestampUTC,
                    UploadBatchID,
                    UploadID,
                    FileName,
                    SourceSheet,
                    ExcelRowNumber,
                    IndicatorID,
                    FieldName,
                    OldValue,
                    NewValue,
                    ChangedBy,
                    ChangeReason
                FROM data_change_log
                WHERE UploadBatchID = ?
                ORDER BY
                    ChangeTimestampUTC DESC,
                    ChangeID DESC
                """,
                conn,
                params=[
                    upload_batch_id
                ]
            )
        )

    finally:

        conn.close()

    return change_history


def save_staged_record_changes(
    upload_batch_id,
    upload_id,
    edited_record,
    changed_by,
    change_reason
):

    change_timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = sqlite3.connect(
        DB_FILE
    )

    try:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        batch_record = conn.execute(
            """
            SELECT
                FileName,
                UploadStatus
            FROM itt_upload_batches
            WHERE UploadBatchID = ?
            """,
            (
                upload_batch_id,
            )
        ).fetchone()

        if batch_record is None:

            raise ValueError(
                "The selected upload batch "
                "could not be found."
            )

        file_name = batch_record[0]

        batch_status = str(
            batch_record[1]
        )

        if batch_status == "Approved":

            raise ValueError(
                "Approved datasets are locked. "
                "Reopen governance must be completed "
                "before editing an approved batch."
            )

        stored_row = conn.execute(
            """
            SELECT
                SourceSheet,
                RowNumber,
                RecordJSON,
                RecordHash
            FROM uploaded_itt_staging
            WHERE UploadBatchID = ?
              AND UploadID = ?
            """,
            (
                upload_batch_id,
                int(upload_id)
            )
        ).fetchone()

        if stored_row is None:

            raise ValueError(
                "The selected staged record "
                "could not be found."
            )

        source_sheet = stored_row[0]

        excel_row_number = stored_row[1]

        previous_record_json = (
            stored_row[2]
        )

        previous_record_hash = (
            stored_row[3]
        )

        original_record = json.loads(
            previous_record_json
        )

        updated_record = (
            original_record.copy()
        )

        changed_fields = []

        all_fields = list(
            dict.fromkeys(
                list(
                    original_record.keys()
                )
                + list(
                    edited_record.keys()
                )
            )
        )

        for field_name in all_fields:

            old_value = (
                original_record.get(
                    field_name
                )
            )

            raw_new_value = (
                edited_record.get(
                    field_name
                )
            )

            new_value = normalize_edited_value(
                raw_new_value,
                old_value
            )

            if not values_are_equal(
                old_value,
                new_value
            ):

                updated_record[
                    field_name
                ] = new_value

                changed_fields.append(
                    {
                        "FieldName":
                            field_name,

                        "OldValue":
                            old_value,

                        "NewValue":
                            new_value
                    }
                )

        if not changed_fields:

            conn.rollback()

            return {
                "Saved":
                    False,

                "ChangedFields":
                    0,

                "Message":
                    "No field changes were detected."
            }

        updated_record_json = json.dumps(
            updated_record,
            ensure_ascii=False,
            sort_keys=False,
            default=str
        )

        new_record_hash = (
            create_staged_record_hash(
                source_sheet,
                excel_row_number,
                updated_record_json
            )
        )

        conn.execute(
            """
            UPDATE uploaded_itt_staging
            SET
                RecordJSON = ?,
                RecordHash = ?,
                UploadStatus = ?
            WHERE UploadBatchID = ?
              AND UploadID = ?
            """,
            (
                updated_record_json,
                new_record_hash,
                "Pending Review",
                upload_batch_id,
                int(upload_id)
            )
        )

        indicator_id = (
            updated_record.get(
                "IndicatorID"
            )
        )

        audit_rows = [
            (
                change_timestamp,
                upload_batch_id,
                int(upload_id),
                file_name,
                source_sheet,
                int(
                    excel_row_number
                ),
                (
                    None
                    if indicator_id is None
                    else str(
                        indicator_id
                    )
                ),
                change[
                    "FieldName"
                ],
                (
                    None
                    if change[
                        "OldValue"
                    ] is None
                    else str(
                        change[
                            "OldValue"
                        ]
                    )
                ),
                (
                    None
                    if change[
                        "NewValue"
                    ] is None
                    else str(
                        change[
                            "NewValue"
                        ]
                    )
                ),
                changed_by,
                change_reason,
                previous_record_hash,
                new_record_hash
            )
            for change in changed_fields
        ]

        conn.executemany(
            """
            INSERT INTO data_change_log (
                ChangeTimestampUTC,
                UploadBatchID,
                UploadID,
                FileName,
                SourceSheet,
                ExcelRowNumber,
                IndicatorID,
                FieldName,
                OldValue,
                NewValue,
                ChangedBy,
                ChangeReason,
                PreviousRecordHash,
                NewRecordHash
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            audit_rows
        )

        conn.execute(
            """
            UPDATE itt_upload_batches
            SET
                UploadStatus = ?,
                ApprovedTimestampUTC = NULL,
                ApprovedBy = NULL
            WHERE UploadBatchID = ?
            """,
            (
                "Pending Review",
                upload_batch_id
            )
        )

        conn.commit()

        return {
            "Saved":
                True,

            "ChangedFields":
                len(
                    changed_fields
                ),

            "Message": (
                f"{len(changed_fields)} "
                "field change(s) saved."
            )
        }

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
# DATA QUALITY SUMMARY CALCULATIONS
# ==================================================

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
# ==================================================
# CLICKABLE QUALITY SUMMARY
# ==================================================

if "quality_issue_filter" not in st.session_state:

    st.session_state[
        "quality_issue_filter"
    ] = "All Records"


quality_controls = [
    {
        "Label": "All Records",
        "Count": len(quality_itt),
        "FlagColumn": None,
        "ButtonKey": "quality_all"
    },
    {
        "Label": "Rows Requiring Review",
        "Count": issue_rows,
        "FlagColumn": "_QualityIssueCount",
        "ButtonKey": "quality_any_issue"
    },
    {
        "Label": "Missing Indicator Codes",
        "Count": missing_indicator_ids,
        "FlagColumn": "_Issue_MissingIndicatorID",
        "ButtonKey": "quality_missing_id"
    },
    {
        "Label": "Duplicate Indicator Codes",
        "Count": duplicate_indicator_ids,
        "FlagColumn": "_Issue_DuplicateIndicatorID",
        "ButtonKey": "quality_duplicate_id"
    },
    {
        "Label": "Missing Units",
        "Count": missing_units,
        "FlagColumn": "_Issue_MissingUnit",
        "ButtonKey": "quality_missing_unit"
    },
    {
        "Label": "Missing LoP Targets",
        "Count": missing_lop_targets,
        "FlagColumn": "_Issue_MissingLoPTarget",
        "ButtonKey": "quality_missing_lop"
    },
    {
        "Label": "Negative Values",
        "Count": negative_values,
        "FlagColumn": "_Issue_NegativeValue",
        "ButtonKey": "quality_negative"
    }
]


quality_card_columns = st.columns(4)

for control_index, control in enumerate(
    quality_controls
):

    with quality_card_columns[
        control_index % 4
    ]:

        st.metric(
            control["Label"],
            f"{int(control['Count']):,}"
        )

        if st.button(
            "View / Edit",
            key=control["ButtonKey"]
        ):

            st.session_state[
                "quality_issue_filter"
            ] = control["Label"]

            st.rerun()


selected_quality_issue = (
    st.session_state[
        "quality_issue_filter"
    ]
)

st.info(
    f"Current quality view: "
    f"**{selected_quality_issue}**"
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
quality_filter_map = {
    "Missing Indicator Codes":
        "_Issue_MissingIndicatorID",

    "Duplicate Indicator Codes":
        "_Issue_DuplicateIndicatorID",

    "Missing Units":
        "_Issue_MissingUnit",

    "Missing LoP Targets":
        "_Issue_MissingLoPTarget",

    "Negative Values":
        "_Issue_NegativeValue"
}


if (
    selected_quality_issue
    == "Rows Requiring Review"
):

    filtered_itt = filtered_itt[
        filtered_itt[
            "_QualityIssueCount"
        ].gt(0)
    ]


elif (
    selected_quality_issue
    in quality_filter_map
):

    flag_column = (
        quality_filter_map[
            selected_quality_issue
        ]
    )

    filtered_itt = filtered_itt[
        filtered_itt[
            flag_column
        ]
    ]

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
# BULK MISSING LOP TARGET CORRECTION
# ==================================================

st.divider()

st.subheader(
    "Bulk Quality Correction"
)

st.caption(
    "Select Missing LoP Targets in the quality summary "
    "to display affected records and enter corrections "
    "in one controlled workspace."
)


batch_is_approved_for_bulk = (
    str(
        selected_batch[
            "UploadStatus"
        ]
    )
    == "Approved"
)


if batch_is_approved_for_bulk:

    st.info(
        "This dataset has already been approved and "
        "is locked against bulk editing."
    )


elif (
    selected_quality_issue
    != "Missing LoP Targets"
):

    st.info(
        "Click **View Records** under "
        "**Missing LoP Targets** to activate the "
        "bulk correction workspace."
    )


elif filtered_itt.empty:

    st.success(
        "No missing Life-of-Project targets remain "
        "for the selected filters."
    )


else:

    st.write(
        f"Records requiring LoP target correction: "
        f"**{len(filtered_itt):,}**"
    )


    bulk_columns = [
        column
        for column in [
            "_UploadID",
            "_SourceSheet",
            "_ExcelRowNumber",
            "Project",
            "Indicators",
            "IndicatorID",
            "ProjectCode",
            "ResultLevelStandard",
            "Unit of Measure",
            "Project Life Target"
        ]
        if column in filtered_itt.columns
    ]


    bulk_lop_source = (
        filtered_itt[
            bulk_columns
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )


    protected_bulk_columns = [
        column
        for column in bulk_columns
        if column
        != "Project Life Target"
    ]


    st.warning(
        "Only **Project Life Target** is editable in "
        "this workspace. Identity and context fields "
        "are locked."
    )


    bulk_lop_editor = st.data_editor(
        bulk_lop_source,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=protected_bulk_columns,
        height=500,
        key=(
            "dashboard10_bulk_lop_editor"
        )
    )


    bulk_column1, bulk_column2 = (
        st.columns(2)
    )


    with bulk_column1:

        bulk_lop_changed_by = (
            st.text_input(
                "Bulk correction made by",
                placeholder=(
                    "Enter reviewer name"
                ),
                key=(
                    "dashboard10_"
                    "bulk_lop_changed_by"
                )
            )
        )


    with bulk_column2:

        bulk_lop_reason = (
            st.text_input(
                "Reason for correction",
                placeholder=(
                    "Example: Completed from the "
                    "approved indicator reference sheet"
                ),
                key=(
                    "dashboard10_"
                    "bulk_lop_reason"
                )
            )
        )


    bulk_lop_confirmation = (
        st.checkbox(
            "I confirm that these Life-of-Project "
            "targets were checked against an "
            "authorized source.",
            key=(
                "dashboard10_"
                "bulk_lop_confirmation"
            )
        )
    )


    bulk_lop_save_disabled = not (
        bulk_lop_changed_by.strip()
        and bulk_lop_reason.strip()
        and bulk_lop_confirmation
    )


    bulk_lop_save_button = st.button(
        "Save Missing LoP Target Corrections",
        type="primary",
        disabled=bulk_lop_save_disabled,
        key=(
            "dashboard10_"
            "save_bulk_lop_corrections"
        )
    )


    if bulk_lop_save_button:

        saved_records = 0

        changed_fields = 0

        unchanged_records = 0

        failed_records = []


        total_records = len(
            bulk_lop_editor
        )


        progress_bar = st.progress(0)


        for row_number, (
            _,
            edited_row
        ) in enumerate(
            bulk_lop_editor.iterrows(),
            start=1
        ):

            upload_id = int(
                edited_row[
                    "_UploadID"
                ]
            )


            original_match = (
                uploaded_itt[
                    uploaded_itt[
                        "_UploadID"
                    ].eq(
                        upload_id
                    )
                ]
            )


            if original_match.empty:

                failed_records.append(
                    {
                        "UploadID":
                            upload_id,

                        "IndicatorID":
                            edited_row.get(
                                "IndicatorID"
                            ),

                        "Error":
                            "The original staged "
                            "record was not found."
                    }
                )

                progress_bar.progress(
                    row_number
                    / max(
                        total_records,
                        1
                    )
                )

                continue


            original_row = (
                original_match.iloc[0]
            )


            # Start with the complete original ITT row.
            # Only the LoP target is replaced.

            complete_edited_record = {
                column:
                original_row[
                    column
                ]
                for column in original_columns
                if column in original_row.index
            }


            complete_edited_record[
                "Project Life Target"
            ] = edited_row[
                "Project Life Target"
            ]


            try:

                save_result = (
                    save_staged_record_changes(
                        upload_batch_id=(
                            selected_batch_id
                        ),
                        upload_id=upload_id,
                        edited_record=(
                            complete_edited_record
                        ),
                        changed_by=(
                            bulk_lop_changed_by
                            .strip()
                        ),
                        change_reason=(
                            bulk_lop_reason
                            .strip()
                        )
                    )
                )


                if save_result["Saved"]:

                    saved_records += 1

                    changed_fields += int(
                        save_result[
                            "ChangedFields"
                        ]
                    )


                else:

                    unchanged_records += 1


            except Exception as error:

                failed_records.append(
                    {
                        "UploadID":
                            upload_id,

                        "IndicatorID":
                            complete_edited_record
                            .get(
                                "IndicatorID"
                            ),

                        "Error":
                            str(error)
                    }
                )


            progress_bar.progress(
                row_number
                / max(
                    total_records,
                    1
                )
            )


        st.cache_data.clear()


        if saved_records > 0:

            st.success(
                f"✅ Saved {changed_fields:,} "
                f"LoP target correction(s) across "
                f"{saved_records:,} record(s)."
            )


        if unchanged_records > 0:

            st.info(
                f"{unchanged_records:,} record(s) "
                "contained no detected changes."
            )


        if failed_records:

            st.error(
                f"{len(failed_records):,} record(s) "
                "could not be saved."
            )

            st.dataframe(
                pd.DataFrame(
                    failed_records
                ),
                hide_index=True,
                use_container_width=True
            )


        if (
            saved_records > 0
            and not failed_records
        ):

            st.info(
                "The batch remains Pending Review. "
                "The Missing LoP Targets count will "
                "now be recalculated."
            )

            st.rerun()




# ==================================================
# BULK MISSING UNITS CORRECTION
# ==================================================

st.divider()

st.subheader(
    "Bulk Missing Units Correction"
)

if (
    selected_quality_issue
    == "Missing Units"
):

    st.success(
        "✅ Missing Units workspace activated"
    )



# ==================================================
# RECORD EDITING AND AUDIT LOG
# ==================================================

st.divider()


st.subheader(
    "Edit Selected ITT Record"
)


st.caption(
    "Select one staged ITT row, update its original "
    "uploaded fields, and save the corrections before "
    "dataset approval."
)


batch_is_approved = (
    str(
        selected_batch[
            "UploadStatus"
        ]
    )
    == "Approved"
)


if batch_is_approved:

    st.info(
        "This batch is approved and locked against "
        "record editing."
    )


else:

    selection_source = (
        filtered_itt.copy()
    )

    if selection_source.empty:

        st.warning(
            "No records match the current search "
            "and filter selections."
        )

    else:

        record_labels = {}

        for _, record_row in (
            selection_source.iterrows()
        ):

            upload_id = int(
                record_row[
                    "_UploadID"
                ]
            )

            indicator_code = str(
                record_row.get(
                    "IndicatorID",
                    ""
                )
                or ""
            )

            project_name = str(
                record_row.get(
                    "Project",
                    ""
                )
                or ""
            )

            indicator_text = str(
                record_row.get(
                    "Indicators",
                    ""
                )
                or ""
            )

            shortened_indicator = (
                indicator_text[:80]
            )

            record_label = (
                f"{indicator_code or 'No IndicatorID'}"
                f" | {project_name}"
                f" | Row "
                f"{int(record_row['_ExcelRowNumber'])}"
                f" | {shortened_indicator}"
                f" | UploadID {upload_id}"
            )

            record_labels[
                record_label
            ] = upload_id


        selected_record_label = (
            st.selectbox(
                "Select record to edit",
                options=list(
                    record_labels.keys()
                ),
                key=(
                    "dashboard10_"
                    "record_selector"
                )
            )
        )


        selected_upload_id = (
            record_labels[
                selected_record_label
            ]
        )


        selected_record_row = (
            uploaded_itt[
                uploaded_itt[
                    "_UploadID"
                ].eq(
                    selected_upload_id
                )
            ]
            .iloc[0]
        )


        editable_columns = [
            column
            for column in (
                original_columns
            )
            if column in (
                uploaded_itt.columns
            )
        ]


        editable_record = pd.DataFrame(
            [
                {
                    column:
                    selected_record_row[
                        column
                    ]
                    for column in (
                        editable_columns
                    )
                }
            ]
        )


        st.warning(
            "Changes are saved only after clicking "
            "**Save Record Changes**. ETL is not run."
        )


        edited_record_dataframe = (
            st.data_editor(
                editable_record,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key=(
                    "dashboard10_"
                    f"editor_{selected_upload_id}"
                )
            )
        )


        editor1, editor2 = (
            st.columns(2)
        )


        with editor1:

            changed_by = st.text_input(
                "Changed by",
                placeholder=(
                    "Enter the reviewer name"
                ),
                key=(
                    "dashboard10_"
                    f"changed_by_{selected_upload_id}"
                )
            )


        with editor2:

            change_reason = (
                st.text_input(
                    "Reason for change",
                    placeholder=(
                        "Example: Corrected against "
                        "approved source report"
                    ),
                    key=(
                        "dashboard10_"
                        f"reason_{selected_upload_id}"
                    )
                )
            )


        save_confirmation = st.checkbox(
            "I confirm that the edited values were "
            "checked against an authorized source.",
            key=(
                "dashboard10_"
                f"edit_confirmation_"
                f"{selected_upload_id}"
            )
        )


        save_changes_disabled = not (
            changed_by.strip()
            and change_reason.strip()
            and save_confirmation
        )


        save_changes_button = st.button(
            "Save Record Changes",
            type="primary",
            disabled=(
                save_changes_disabled
            ),
            key=(
                "dashboard10_"
                f"save_record_"
                f"{selected_upload_id}"
            )
        )


        if save_changes_button:

            edited_record = (
                edited_record_dataframe
                .iloc[0]
                .to_dict()
            )

            try:

                save_result = (
                    save_staged_record_changes(
                        upload_batch_id=(
                            selected_batch_id
                        ),
                        upload_id=(
                            selected_upload_id
                        ),
                        edited_record=(
                            edited_record
                        ),
                        changed_by=(
                            changed_by.strip()
                        ),
                        change_reason=(
                            change_reason.strip()
                        )
                    )
                )


                if save_result["Saved"]:

                    st.cache_data.clear()

                    st.success(
                        "✅ "
                        + save_result[
                            "Message"
                        ]
                    )

                    st.info(
                        "The batch remains Pending Review. "
                        "Quality checks will be recalculated."
                    )

                    st.rerun()


                else:

                    st.info(
                        save_result[
                            "Message"
                        ]
                    )


            except Exception as error:

                st.error(
                    "The record changes could "
                    "not be saved."
                )

                st.exception(
                    error
                )


st.markdown(
    "### Change Audit Log"
)


change_history = load_change_history(
    selected_batch_id
)


if change_history.empty:

    st.info(
        "No record changes have been logged "
        "for this upload."
    )


else:

    audit_indicator_options = sorted(
        value
        for value in (
            change_history[
                "IndicatorID"
            ]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if value
    )


    selected_audit_indicators = (
        st.multiselect(
            "Filter audit log by Indicator Code",
            options=audit_indicator_options,
            default=[],
            key=(
                "dashboard10_"
                "audit_indicator_filter"
            )
        )
    )


    filtered_change_history = (
        change_history.copy()
    )


    if selected_audit_indicators:

        filtered_change_history = (
            filtered_change_history[
                filtered_change_history[
                    "IndicatorID"
                ]
                .astype(str)
                .isin(
                    selected_audit_indicators
                )
            ]
        )


    st.dataframe(
        filtered_change_history,
        hide_index=True,
        use_container_width=True,
        column_config={
            "ChangeID":
                st.column_config.NumberColumn(
                    "Change ID",
                    format="%d"
                ),

            "UploadID":
                st.column_config.NumberColumn(
                    "Upload ID",
                    format="%d"
                ),

            "ExcelRowNumber":
                st.column_config.NumberColumn(
                    "Excel Row",
                    format="%d"
                )
        }
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

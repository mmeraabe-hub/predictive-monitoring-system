import hashlib
import io
import json
import sqlite3
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st

from utils.database_utils import DB_FILE


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Upload Existing ITT",
    page_icon="📤",
    layout="wide"
)


st.title(
    "Upload Existing ITT"
)


st.caption(
    "Upload an Excel ITT for staging, preview, "
    "data review, cleaning, and approval before ETL."
)


st.info(
    """
    The uploaded workbook is stored in the staging area.

    Uploading does not run ETL, replace dashboard data,
    retrain a model, or promote a model version.

    A reviewer must inspect and approve the staged dataset
    before it proceeds to the transformation pipeline.
    """
)


# ==================================================
# DATABASE INITIALIZATION
# ==================================================

def initialize_upload_tables():

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
            CREATE INDEX IF NOT EXISTS
            idx_staging_batch
            ON uploaded_itt_staging (
                UploadBatchID
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_staging_status
            ON uploaded_itt_staging (
                UploadStatus
            )
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_staging_record_hash
            ON uploaded_itt_staging (
                UploadBatchID,
                RecordHash
            )
            """
        )

        conn.commit()

    finally:

        conn.close()


initialize_upload_tables()


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def normalize_json_value(value):

    if value is None:

        return None

    try:

        if pd.isna(value):

            return None

    except TypeError:

        pass

    if isinstance(
        value,
        (
            pd.Timestamp,
            datetime
        )
    ):

        return value.isoformat()

    if isinstance(
        value,
        (
            np.integer,
        )
    ):

        return int(value)

    if isinstance(
        value,
        (
            np.floating,
        )
    ):

        return float(value)

    if isinstance(
        value,
        (
            np.bool_,
        )
    ):

        return bool(value)

    return value


def row_to_json(row):

    clean_record = {
        str(column):
        normalize_json_value(value)
        for column, value in row.items()
    }

    return json.dumps(
        clean_record,
        ensure_ascii=False,
        sort_keys=False,
        default=str
    )


def create_record_hash(
    source_sheet,
    row_number,
    record_json
):

    hash_input = (
        f"{source_sheet}|"
        f"{row_number}|"
        f"{record_json}"
    )

    return hashlib.sha256(
        hash_input.encode("utf-8")
    ).hexdigest()


def load_existing_file_hashes():

    conn = sqlite3.connect(DB_FILE)

    try:

        hash_data = pd.read_sql_query(
            """
            SELECT DISTINCT FileHash
            FROM itt_upload_batches
            """,
            conn
        )

    finally:

        conn.close()

    return set(
        hash_data["FileHash"]
        .dropna()
        .astype(str)
        .tolist()
    )


def save_workbook_to_staging(
    file_name,
    file_bytes,
    workbook_sheets
):

    upload_timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    upload_batch_id = str(
        uuid.uuid4()
    )

    file_hash = hashlib.sha256(
        file_bytes
    ).hexdigest()

    existing_hashes = (
        load_existing_file_hashes()
    )

    if file_hash in existing_hashes:

        raise ValueError(
            "This exact workbook has already been "
            "uploaded to the staging area."
        )

    staging_rows = []

    total_rows = 0

    maximum_columns = 0

    for sheet_name, sheet_data in (
        workbook_sheets.items()
    ):

        total_rows += len(sheet_data)

        maximum_columns = max(
            maximum_columns,
            len(sheet_data.columns)
        )

        for dataframe_index, row in (
            sheet_data.iterrows()
        ):

            record_json = row_to_json(row)

            excel_row_number = (
                int(dataframe_index)
                + 2
            )

            record_hash = create_record_hash(
                sheet_name,
                excel_row_number,
                record_json
            )

            staging_rows.append(
                {
                    "UploadTimestamp":
                        upload_timestamp,

                    "FileName":
                        file_name,

                    "SourceSheet":
                        sheet_name,

                    "RowNumber":
                        excel_row_number,

                    "RecordJSON":
                        record_json,

                    "UploadStatus":
                        "Pending Review",

                    "UploadBatchID":
                        upload_batch_id,

                    "RecordHash":
                        record_hash
                }
            )

    staging_dataframe = pd.DataFrame(
        staging_rows
    )

    batch_dataframe = pd.DataFrame(
        [
            {
                "UploadBatchID":
                    upload_batch_id,

                "UploadTimestampUTC":
                    upload_timestamp,

                "FileName":
                    file_name,

                "FileHash":
                    file_hash,

                "SheetCount":
                    len(workbook_sheets),

                "RowCount":
                    total_rows,

                "ColumnCountMaximum":
                    maximum_columns,

                "UploadStatus":
                    "Pending Review",

                "ReviewNotes":
                    None,

                "ApprovedTimestampUTC":
                    None,

                "ApprovedBy":
                    None
            }
        ]
    )

    conn = sqlite3.connect(DB_FILE)

    try:

        conn.execute(
            "BEGIN"
        )

        batch_dataframe.to_sql(
            "itt_upload_batches",
            conn,
            if_exists="append",
            index=False
        )

        staging_dataframe.to_sql(
            "uploaded_itt_staging",
            conn,
            if_exists="append",
            index=False
        )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()

    return {
        "UploadBatchID":
            upload_batch_id,

        "FileName":
            file_name,

        "SheetCount":
            len(workbook_sheets),

        "RowCount":
            total_rows,

        "ColumnCountMaximum":
            maximum_columns,

        "UploadStatus":
            "Pending Review"
    }


# ==================================================
# FILE UPLOAD
# ==================================================

uploaded_file = st.file_uploader(
    "Upload an Excel ITT",
    type=[
        "xlsx"
    ],
    help=(
        "The workbook will be staged for review. "
        "It will not run ETL automatically."
    )
)


if uploaded_file is not None:

    file_bytes = uploaded_file.getvalue()

    file_buffer = io.BytesIO(
        file_bytes
    )

    try:

        workbook = pd.ExcelFile(
            file_buffer,
            engine="openpyxl"
        )

        workbook_sheets = {}

        for sheet_name in workbook.sheet_names:

            workbook_sheets[
                sheet_name
            ] = pd.read_excel(
                workbook,
                sheet_name=sheet_name
            )

    except Exception as error:

        st.error(
            "The uploaded workbook could not be read."
        )

        st.exception(error)

        st.stop()


    sheet_summary = pd.DataFrame(
        [
            {
                "Sheet":
                    sheet_name,

                "Rows":
                    len(sheet_data),

                "Columns":
                    len(sheet_data.columns)
            }
            for sheet_name, sheet_data
            in workbook_sheets.items()
        ]
    )


    st.subheader(
        "Upload Preview"
    )


    preview1, preview2, preview3 = (
        st.columns(3)
    )


    preview1.metric(
        "Sheets",
        len(workbook_sheets)
    )


    preview2.metric(
        "Total Rows",
        int(
            sheet_summary[
                "Rows"
            ].sum()
        )
    )


    preview3.metric(
        "Maximum Columns",
        int(
            sheet_summary[
                "Columns"
            ].max()
        )
    )


    st.dataframe(
        sheet_summary,
        hide_index=True,
        use_container_width=True
    )


    selected_preview_sheet = (
        st.selectbox(
            "Preview Sheet",
            options=list(
                workbook_sheets.keys()
            )
        )
    )


    preview_data = workbook_sheets[
        selected_preview_sheet
    ]


    st.write(
        f"Previewing the first 20 rows from "
        f"**{selected_preview_sheet}**"
    )


    st.dataframe(
        preview_data.head(20),
        hide_index=True,
        use_container_width=True
    )


    required_identity_columns = {
        "Project",
        "Indicators",
        "IndicatorID",
        "ProjectCode"
    }


    preview_columns = {
        str(column).strip()
        for column in (
            preview_data.columns
        )
    }


    missing_identity_columns = (
        required_identity_columns
        - preview_columns
    )


    if missing_identity_columns:

        st.warning(
            "The selected sheet is missing expected "
            "ITT identity columns: "
            + ", ".join(
                sorted(
                    missing_identity_columns
                )
            )
        )

    else:

        st.success(
            "The selected sheet contains the expected "
            "ITT identity columns."
        )


    confirmation = st.checkbox(
        "I confirm that this workbook should be "
        "saved for data review."
    )


    save_button = st.button(
        "Save Workbook to Staging",
        type="primary",
        disabled=not confirmation
    )


    if save_button:

        try:

            saved_summary = (
                save_workbook_to_staging(
                    file_name=(
                        uploaded_file.name
                    ),
                    file_bytes=file_bytes,
                    workbook_sheets=(
                        workbook_sheets
                    )
                )
            )


            st.cache_data.clear()


            st.success(
                "✅ The uploaded ITT was saved "
                "successfully for review."
            )


            st.json(
                saved_summary
            )


            st.info(
                "Upload status: Pending Review. "
                "No ETL or model retraining has run."
            )


        except ValueError as error:

            st.warning(
                str(error)
            )


        except Exception as error:

            st.error(
                "The workbook could not be saved "
                "to the staging database."
            )

            st.exception(error)


# ==================================================
# RECENT UPLOADS
# ==================================================

st.divider()

st.subheader(
    "Recent Staged Uploads"
)


@st.cache_data
def load_recent_uploads():

    conn = sqlite3.connect(DB_FILE)

    try:

        uploads = pd.read_sql_query(
            """
            SELECT
                UploadBatchID,
                UploadTimestampUTC,
                FileName,
                SheetCount,
                RowCount,
                ColumnCountMaximum,
                UploadStatus
            FROM itt_upload_batches
            ORDER BY UploadTimestampUTC DESC
            """,
            conn
        )

    finally:

        conn.close()

    return uploads


recent_uploads = load_recent_uploads()


if recent_uploads.empty:

    st.info(
        "No ITT workbooks are currently staged."
    )

else:

    st.dataframe(
        recent_uploads,
        hide_index=True,
        use_container_width=True
    )


st.caption(
    "Staged uploads are awaiting review and approval. "
    "The transformation pipeline is not started by "
    "this page."
)

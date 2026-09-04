
import sqlite3
import pandas as pd
import os

CURRENT_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

APP_FOLDER = os.path.dirname(
    CURRENT_FOLDER
)

DB_FILE = os.path.join(
    APP_FOLDER,
    "predictive_monitoring.db"
)

def load_dashboard_data_sqlite():

    conn = sqlite3.connect(DB_FILE)

    data = pd.read_sql(
        """
        SELECT *
        FROM dashboard_data
        """,
        conn
    )

    conn.close()

    return data

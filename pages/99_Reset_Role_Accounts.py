import streamlit as st
import sqlite3

from auth import (
    hash_password,
    utc_now,
    to_iso,
    current_user,
)

user = current_user()

if "Admin" not in user.get("roles", []):
    st.error("Admin access required")
    st.stop()

st.title("Reset Role Accounts")

if st.button("Reset Data Entry"):
    conn = sqlite3.connect("predictive_monitoring.db")

    conn.execute(
        """
        UPDATE auth_users
        SET
            PasswordHash=?,
            FailedAttempts=0,
            LockedUntilUTC=NULL,
            MustChangePassword=1,
            UpdatedUTC=?
        WHERE Username='dataentry'
        """,
        (
            hash_password("DataEntry@2026!"),
            to_iso(utc_now()),
        )
    )

    conn.commit()
    conn.close()

    st.success("Data Entry account reset")
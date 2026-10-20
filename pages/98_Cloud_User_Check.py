import streamlit as st
import sqlite3

st.title("Cloud User Check")

conn = sqlite3.connect("predictive_monitoring.db")

rows = conn.execute("""
SELECT
    Username,
    IsActive,
    FailedAttempts,
    LockedUntilUTC,
    MustChangePassword
FROM auth_users
ORDER BY Username
""").fetchall()

st.write(rows)

conn.close()
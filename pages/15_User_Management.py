import secrets
import sqlite3
import streamlit as st

from auth import (
    DB_PATH, audit, create_user, db_connection, hash_password, initialize_auth_schema,
    require_login, to_iso, utc_now,
)

st.set_page_config(page_title="User Management", page_icon="🔐", layout="wide")
admin = require_login("*")
initialize_auth_schema()
st.title("🔐 User Management")


def get_roles():
    with db_connection() as conn:
        return [r["RoleName"] for r in conn.execute("SELECT RoleName FROM auth_roles ORDER BY RoleName")]


def get_users():
    with db_connection() as conn:
        return conn.execute(
            """
            SELECT u.UserID, u.Username, u.FullName, u.Email, u.IsActive,
                   u.MustChangePassword, u.LastLoginUTC,
                   COALESCE(GROUP_CONCAT(r.RoleName, ', '), '') AS Roles
            FROM auth_users u
            LEFT JOIN auth_user_roles ur ON ur.UserID=u.UserID
            LEFT JOIN auth_roles r ON r.RoleID=ur.RoleID
            GROUP BY u.UserID
            ORDER BY u.FullName, u.Username
            """
        ).fetchall()


roles = get_roles()
tab1, tab2, tab3 = st.tabs(["Users", "Create User", "Audit Log"])

with tab1:
    users = get_users()
    st.dataframe([dict(row) for row in users], use_container_width=True, hide_index=True)
    if users:
        labels = {f"{u['FullName']} ({u['Username']})": u for u in users}
        selected_label = st.selectbox("Select a user", list(labels))
        selected = labels[selected_label]
        selected_id = int(selected["UserID"])
        selected_roles = [r.strip() for r in selected["Roles"].split(",") if r.strip()]

        with st.form("edit_user_form"):
            full_name = st.text_input("Full name", value=selected["FullName"])
            email = st.text_input("Email", value=selected["Email"] or "")
            new_roles = st.multiselect("Roles", roles, default=selected_roles)
            is_active = st.checkbox("Active", value=bool(selected["IsActive"]))
            save = st.form_submit_button("Save changes", type="primary")
        if save:
            if selected_id == admin["user_id"] and not is_active:
                st.error("You cannot deactivate your own signed-in account.")
            elif not new_roles:
                st.error("Select at least one role.")
            else:
                try:
                    with db_connection() as conn:
                        conn.execute(
                            "UPDATE auth_users SET FullName=?, Email=?, IsActive=?, UpdatedUTC=? WHERE UserID=?",
                            (full_name.strip(), email.strip().lower() or None, int(is_active), to_iso(utc_now()), selected_id),
                        )
                        conn.execute("DELETE FROM auth_user_roles WHERE UserID=?", (selected_id,))
                        conn.executemany(
                            "INSERT INTO auth_user_roles(UserID, RoleID) SELECT ?, RoleID FROM auth_roles WHERE RoleName=?",
                            [(selected_id, role) for role in new_roles],
                        )
                    audit("USER_UPDATED", f"Updated {selected['Username']}", admin["user_id"], admin["username"])
                    st.success("User updated.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That email address is already assigned to another user.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate temporary password", use_container_width=True):
                temporary = secrets.token_urlsafe(14) + "aA1!"
                with db_connection() as conn:
                    conn.execute(
                        "UPDATE auth_users SET PasswordHash=?, MustChangePassword=1, FailedAttempts=0, LockedUntilUTC=NULL, UpdatedUTC=? WHERE UserID=?",
                        (hash_password(temporary), to_iso(utc_now()), selected_id),
                    )
                audit("PASSWORD_RESET_BY_ADMIN", f"Reset {selected['Username']}", admin["user_id"], admin["username"])
                st.success("Temporary password generated. Share it through an approved secure channel; it is shown only now.")
                st.code(temporary)
        with col2:
            if st.button("Unlock account", use_container_width=True):
                with db_connection() as conn:
                    conn.execute(
                        "UPDATE auth_users SET FailedAttempts=0, LockedUntilUTC=NULL, UpdatedUTC=? WHERE UserID=?",
                        (to_iso(utc_now()), selected_id),
                    )
                audit("ACCOUNT_UNLOCKED", f"Unlocked {selected['Username']}", admin["user_id"], admin["username"])
                st.success("Account unlocked.")

with tab2:
    with st.form("create_user_form", clear_on_submit=True):
        username = st.text_input("Username")
        full_name = st.text_input("Full name")
        email = st.text_input("Email (optional)")
        selected_roles = st.multiselect("Roles", roles)
        password = st.text_input("Temporary password", type="password")
        confirm = st.text_input("Confirm temporary password", type="password")
        submitted = st.form_submit_button("Create user", type="primary")
    if submitted:
        if password != confirm:
            st.error("Passwords do not match.")
        else:
            try:
                create_user(username, full_name, email, password, selected_roles, admin["user_id"], True)
                st.success("User created. The user must change the temporary password at first sign-in.")
            except (ValueError, sqlite3.IntegrityError) as exc:
                st.error(f"Could not create user: {exc}")

with tab3:
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT EventUTC, Username, Action, Details FROM auth_audit_log ORDER BY AuditID DESC LIMIT 500"
        ).fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)

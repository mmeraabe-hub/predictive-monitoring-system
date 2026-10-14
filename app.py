import streamlit as st
import sqlite3

try:
    conn = sqlite3.connect("predictive_monitoring.db")

    users = conn.execute(
        "SELECT Username FROM auth_users"
    ).fetchall()

    st.write("CLOUD USERS:", users)

    conn.close()

except Exception as e:
    st.write("DATABASE ERROR:", e)
from auth import (
    clear_session,
    current_user,
    login_screen,
    session_is_valid,
)


# ============================================================
# LOGIN AND LOGOUT FUNCTIONS
# ============================================================

def show_login():
    login_screen()


def logout_user():
    clear_session("LOGOUT")
    st.rerun()


# ============================================================
# LOGIN PAGE
# ============================================================

login_page = st.Page(
    show_login,
    title="Secure Sign In",
    icon="🔐",
    default=True,
)


# ============================================================
# READ-ONLY PAGES AVAILABLE TO EVERY AUTHENTICATED USER
# ============================================================

home_page = st.Page(
    "pages/0_Home.py",
    title="Home",
    icon="🏠",
    default=True,
)

portfolio_page = st.Page(
    "pages/1_Portfolio_Dashboard.py",
    title="Portfolio Dashboard",
    icon="📊",
)

project_page = st.Page(
    "pages/2_Project_Dashboard.py",
    title="Project Dashboard",
    icon="📁",
)

indicator_page = st.Page(
    "pages/3_Indicator_Dashboard.py",
    title="Indicator Dashboard",
    icon="📈",
)

risk_page = st.Page(
    "pages/6_Risk_Classification_Dashboard.py",
    title="Risk Classification",
    icon="⚠️",
)

model_performance_page = st.Page(
    "pages/7_Model_Performance_Dashboard.py",
    title="Model Performance",
    icon="📉",
)

model_lifecycle_page = st.Page(
    "pages/8_Model_Lifecycle_Dashboard.py",
    title="Model Lifecycle",
    icon="🔄",
)

automation_page = st.Page(
    "pages/11_Automation_Monitoring_Dashboard.py",
    title="Automation Monitoring",
    icon="⚙️",
)

forecast_verification_page = st.Page(
    "pages/12_Dynamic_Forecast_Verification_Dashboard.py",
    title="Forecast Verification",
    icon="🔍",
)


# ============================================================
# ROLE-SPECIFIC OPERATIONAL PAGES
# ============================================================

upload_itt_page = st.Page(
    "pages/5_Upload_ITT.py",
    title="Upload ITT",
    icon="📤",
)

review_approval_page = st.Page(
    "pages/10_Data_Review_Approval_Dashboard.py",
    title="Data Review and Approval",
    icon="✅",
)

itt_data_entry_page = st.Page(
    "pages/13_ITT_Data_Entry_Portal.py",
    title="ITT Data Entry",
    icon="✍️",
)

new_indicator_page = st.Page(
    "pages/14_New_Indicator_Registration.py",
    title="New Indicator Registration",
    icon="➕",
)

user_management_page = st.Page(
    "pages/15_User_Management.py",
    title="User Management",
    icon="🔐",
)


# ============================================================
# LOGOUT PAGE
# ============================================================

logout_page = st.Page(
    logout_user,
    title="Sign Out",
    icon="🚪",
)


# ============================================================
# LOGIN-FIRST NAVIGATION
# ============================================================

if not session_is_valid():

    selected_page = st.navigation(
        [
            login_page,
        ],
        position="hidden",
    )

    selected_page.run()
    st.stop()


# ============================================================
# AUTHENTICATED USER
# ============================================================

user = current_user()
roles = set(user.get("roles", []))


# ============================================================
# READ-ONLY DASHBOARDS FOR EVERY AUTHENTICATED USER
# ============================================================

read_only_pages = [
    home_page,
    portfolio_page,
    project_page,
    indicator_page,
    risk_page,
    model_performance_page,
    automation_page,
    forecast_verification_page,
]


# ============================================================
# BUILD ROLE-SPECIFIC WORKSPACE
# ============================================================

workspace_pages = []
administration_pages = []


# Data Entry users can upload, enter, and register data.
if "Data Entry" in roles or "Admin" in roles:
    workspace_pages.extend(
        [
            upload_itt_page,
            itt_data_entry_page,
            new_indicator_page,
        ]
    )


# Reviewers and Approvers can access the review workflow.
if (
    "Reviewer" in roles
    or "Approver" in roles
    or "Admin" in roles
):
    workspace_pages.append(review_approval_page)


# Only administrators can manage users.
if "Admin" in roles:
    administration_pages.extend(
        [
            model_lifecycle_page,
            user_management_page,
        ]
    )


# ============================================================
# CREATE NAVIGATION SECTIONS
# ============================================================

navigation = {
    "Read-Only Dashboards": read_only_pages,
}

if workspace_pages:
    navigation["My Workspace"] = workspace_pages

if administration_pages:
    navigation["Administration"] = administration_pages

navigation["Account"] = [
    logout_page,
]


# ============================================================
# USER INFORMATION
# ============================================================

with st.sidebar:
    st.markdown("---")

    display_name = user.get(
        "full_name",
        user.get("username", "User"),
    )

    st.caption(f"Signed in as **{display_name}**")

    role_display = ", ".join(sorted(roles))

    if role_display:
        st.caption(f"Role: {role_display}")


# ============================================================
# RUN SELECTED AUTHORIZED PAGE
# ============================================================

selected_page = st.navigation(
    navigation,
    position="sidebar",
    expanded=True,
)

selected_page.run()
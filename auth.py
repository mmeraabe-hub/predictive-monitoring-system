from __future__ import annotations

import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import streamlit as st
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError

DB_PATH = Path(os.getenv("APP_DB_PATH", "predictive_monitoring.db"))
PEPPER = os.getenv("APP_PASSWORD_PEPPER", "")
IDLE_TIMEOUT_MINUTES = int(os.getenv("APP_IDLE_TIMEOUT_MINUTES", "30"))
ABSOLUTE_TIMEOUT_HOURS = int(os.getenv("APP_ABSOLUTE_TIMEOUT_HOURS", "8"))
MAX_FAILED_ATTEMPTS = int(os.getenv("APP_MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("APP_LOCKOUT_MINUTES", "15"))

# OWASP-aligned Argon2id baseline: 19 MiB, 2 iterations, parallelism 1.
PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

DEFAULT_ROLE_PERMISSIONS = {
    "Admin": ["*"],
    "Data Entry": ["itt.view", "itt.create", "itt.edit_own", "itt.submit", "indicator.register"],
    "Reviewer": ["itt.view", "itt.review", "itt.return", "indicator.review", "dashboard.view"],
    "Approver": ["itt.view", "itt.review", "itt.return", "itt.approve", "itt.reject", "indicator.approve", "dataset.approve", "dashboard.view"],
    "Management": ["dashboard.view", "forecast.view", "report.view", "repository.view"],
}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def from_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_auth_schema() -> None:
    with db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS auth_users (
                UserID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                FullName TEXT NOT NULL,
                Email TEXT UNIQUE COLLATE NOCASE,
                PasswordHash TEXT NOT NULL,
                IsActive INTEGER NOT NULL DEFAULT 1 CHECK (IsActive IN (0,1)),
                MustChangePassword INTEGER NOT NULL DEFAULT 1 CHECK (MustChangePassword IN (0,1)),
                FailedAttempts INTEGER NOT NULL DEFAULT 0,
                LockedUntilUTC TEXT,
                LastLoginUTC TEXT,
                CreatedUTC TEXT NOT NULL,
                UpdatedUTC TEXT NOT NULL,
                CreatedBy INTEGER,
                FOREIGN KEY (CreatedBy) REFERENCES auth_users(UserID)
            );

            CREATE TABLE IF NOT EXISTS auth_roles (
                RoleID INTEGER PRIMARY KEY AUTOINCREMENT,
                RoleName TEXT NOT NULL UNIQUE,
                Description TEXT
            );

            CREATE TABLE IF NOT EXISTS auth_permissions (
                PermissionID INTEGER PRIMARY KEY AUTOINCREMENT,
                PermissionCode TEXT NOT NULL UNIQUE,
                Description TEXT
            );

            CREATE TABLE IF NOT EXISTS auth_user_roles (
                UserID INTEGER NOT NULL,
                RoleID INTEGER NOT NULL,
                PRIMARY KEY (UserID, RoleID),
                FOREIGN KEY (UserID) REFERENCES auth_users(UserID) ON DELETE CASCADE,
                FOREIGN KEY (RoleID) REFERENCES auth_roles(RoleID) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS auth_role_permissions (
                RoleID INTEGER NOT NULL,
                PermissionID INTEGER NOT NULL,
                PRIMARY KEY (RoleID, PermissionID),
                FOREIGN KEY (RoleID) REFERENCES auth_roles(RoleID) ON DELETE CASCADE,
                FOREIGN KEY (PermissionID) REFERENCES auth_permissions(PermissionID) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS auth_audit_log (
                AuditID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER,
                Username TEXT,
                Action TEXT NOT NULL,
                Details TEXT,
                EventUTC TEXT NOT NULL,
                FOREIGN KEY (UserID) REFERENCES auth_users(UserID)
            );
            """
        )

        for role_name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
            conn.execute(
                "INSERT OR IGNORE INTO auth_roles(RoleName, Description) VALUES (?, ?)",
                (role_name, f"Built-in {role_name} role"),
            )
            for code in permissions:
                conn.execute(
                    "INSERT OR IGNORE INTO auth_permissions(PermissionCode, Description) VALUES (?, ?)",
                    (code, code),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO auth_role_permissions(RoleID, PermissionID)
                    SELECT r.RoleID, p.PermissionID
                    FROM auth_roles r, auth_permissions p
                    WHERE r.RoleName = ? AND p.PermissionCode = ?
                    """,
                    (role_name, code),
                )


def _password_material(password: str) -> str:
    return password + PEPPER


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 12:
        return False, "Password must contain at least 12 characters."
    if len(password) > 128:
        return False, "Password must not exceed 128 characters."
    if not any(c.islower() for c in password):
        return False, "Password must include a lowercase letter."
    if not any(c.isupper() for c in password):
        return False, "Password must include an uppercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must include a number."
    if not any(not c.isalnum() for c in password):
        return False, "Password must include a special character."
    return True, ""


def hash_password(password: str) -> str:
    valid, message = validate_password(password)
    if not valid:
        raise ValueError(message)
    return PASSWORD_HASHER.hash(_password_material(password))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, _password_material(password))
    except (VerifyMismatchError, InvalidHashError):
        return False


def audit(action: str, details: str = "", user_id: int | None = None, username: str | None = None) -> None:
    try:
        with db_connection() as conn:
            conn.execute(
                "INSERT INTO auth_audit_log(UserID, Username, Action, Details, EventUTC) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, action, details[:1000], to_iso(utc_now())),
            )
    except Exception:
        pass


def bootstrap_admin_from_environment() -> bool:
    initialize_auth_schema()
    username = os.getenv("APP_BOOTSTRAP_ADMIN_USERNAME")
    password = os.getenv("APP_BOOTSTRAP_ADMIN_PASSWORD")
    full_name = os.getenv("APP_BOOTSTRAP_ADMIN_FULL_NAME", "System Administrator")
    email = os.getenv("APP_BOOTSTRAP_ADMIN_EMAIL")
    if not username or not password:
        return False
    with db_connection() as conn:
        if conn.execute("SELECT 1 FROM auth_users LIMIT 1").fetchone():
            return False
    create_user(username, full_name, email, password, ["Admin"], None, must_change_password=True)
    return True


def create_user(username: str, full_name: str, email: str | None, password: str,
                roles: Iterable[str], created_by: int | None, must_change_password: bool = True) -> int:
    username = username.strip()
    full_name = full_name.strip()
    email = email.strip().lower() if email and email.strip() else None
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Username must be 3-50 characters using letters, numbers, dot, dash, or underscore.")
    if not full_name:
        raise ValueError("Full name is required.")
    role_list = list(dict.fromkeys(roles))
    if not role_list:
        raise ValueError("Select at least one role.")
    now = to_iso(utc_now())
    password_hash = hash_password(password)
    with db_connection() as conn:
        valid_roles = {
            row["RoleName"] for row in conn.execute(
                f"SELECT RoleName FROM auth_roles WHERE RoleName IN ({','.join('?' for _ in role_list)})",
                role_list,
            )
        }
        if set(role_list) != valid_roles:
            raise ValueError("One or more selected roles are invalid.")
        cursor = conn.execute(
            """
            INSERT INTO auth_users
            (Username, FullName, Email, PasswordHash, IsActive, MustChangePassword,
             FailedAttempts, CreatedUTC, UpdatedUTC, CreatedBy)
            VALUES (?, ?, ?, ?, 1, ?, 0, ?, ?, ?)
            """,
            (username, full_name, email, password_hash, int(must_change_password), now, now, created_by),
        )
        user_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO auth_user_roles(UserID, RoleID)
            SELECT ?, RoleID FROM auth_roles WHERE RoleName = ?
            """,
            [(user_id, role) for role in role_list],
        )
    audit("USER_CREATED", f"Created user {username} with roles {', '.join(role_list)}", created_by)
    return user_id


def authenticate(username: str, password: str) -> dict | None:
    initialize_auth_schema()
    username = username.strip()

    now = utc_now()

    with db_connection() as conn:

        user = conn.execute(
            "SELECT * FROM auth_users WHERE Username = ? COLLATE NOCASE",
            (username,)
        ).fetchone()

 
        if not user:
            try:
                PASSWORD_HASHER.hash(_password_material(password))
            except Exception:
                pass

            audit(
                "LOGIN_FAILED",
                "Unknown username",
                username=username
            )

            return None

        locked_until = from_iso(user["LockedUntilUTC"])

        if locked_until and locked_until > now:
            audit(
                "LOGIN_BLOCKED",
                "Account temporarily locked",
                user["UserID"],
                user["Username"],
            )

            return None

        password_ok = verify_password(
            user["PasswordHash"],
            password
        )

        st.write("PASSWORD ENTERED:", password)
        st.write("PASSWORD VALID:", password_ok)

        if not user["IsActive"] or not password_ok:

            failed = int(user["FailedAttempts"]) + 1

            new_lock = (
                now + timedelta(minutes=LOCKOUT_MINUTES)
                if failed >= MAX_FAILED_ATTEMPTS
                else None
            )

            conn.execute(
                """
                UPDATE auth_users
                SET FailedAttempts=?,
                    LockedUntilUTC=?,
                    UpdatedUTC=?
                WHERE UserID=?
                """,
                (
                    0 if new_lock else failed,
                    to_iso(new_lock),
                    to_iso(now),
                    user["UserID"],
                ),
            )

            audit(
                "LOGIN_FAILED",
                "Invalid credentials or inactive account",
                user["UserID"],
                user["Username"],
            )

            return None

        if PASSWORD_HASHER.check_needs_rehash(
            user["PasswordHash"]
        ):
            conn.execute(
                """
                UPDATE auth_users
                SET PasswordHash=?,
                    UpdatedUTC=?
                WHERE UserID=?
                """,
                (
                    hash_password(password),
                    to_iso(now),
                    user["UserID"],
                ),
            )

        conn.execute(
            """
            UPDATE auth_users
            SET FailedAttempts=0,
                LockedUntilUTC=NULL,
                LastLoginUTC=?,
                UpdatedUTC=?
            WHERE UserID=?
            """,
            (
                to_iso(now),
                to_iso(now),
                user["UserID"],
            ),
        )

        roles = [
            r["RoleName"]
            for r in conn.execute(
                """
                SELECT r.RoleName
                FROM auth_roles r
                JOIN auth_user_roles ur
                    ON ur.RoleID = r.RoleID
                WHERE ur.UserID=?
                ORDER BY r.RoleName
                """,
                (user["UserID"],),
            )
        ]

        permissions = [
            p["PermissionCode"]
            for p in conn.execute(
                """
                SELECT DISTINCT p.PermissionCode
                FROM auth_permissions p
                JOIN auth_role_permissions rp
                    ON rp.PermissionID = p.PermissionID
                JOIN auth_user_roles ur
                    ON ur.RoleID = rp.RoleID
                WHERE ur.UserID=?
                """,
                (user["UserID"],),
            )
        ]

        result = dict(user)
        result["Roles"] = roles
        result["Permissions"] = permissions

    audit(
        "LOGIN_SUCCESS",
        "Successful sign-in",
        result["UserID"],
        result["Username"],
    )

    return result

def establish_session(user: dict) -> None:
    now = utc_now()
    st.session_state.auth = {
        "authenticated": True,
        "session_id": secrets.token_urlsafe(32),
        "user_id": int(user["UserID"]),
        "username": user["Username"],
        "full_name": user["FullName"],
        "roles": list(user["Roles"]),
        "permissions": list(user["Permissions"]),
        "must_change_password": bool(user["MustChangePassword"]),
        "issued_at": to_iso(now),
        "last_activity": to_iso(now),
    }


def clear_session(reason: str = "LOGOUT") -> None:
    auth = st.session_state.get("auth", {})
    if auth.get("authenticated"):
        audit(reason, "Session ended", auth.get("user_id"), auth.get("username"))
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def session_is_valid() -> bool:
    auth = st.session_state.get("auth")
    if not auth or not auth.get("authenticated"):
        return False
    now = utc_now()
    issued = from_iso(auth.get("issued_at"))
    last = from_iso(auth.get("last_activity"))
    if not issued or not last:
        clear_session("SESSION_INVALID")
        return False
    if now - last > timedelta(minutes=IDLE_TIMEOUT_MINUTES):
        clear_session("SESSION_IDLE_TIMEOUT")
        return False
    if now - issued > timedelta(hours=ABSOLUTE_TIMEOUT_HOURS):
        clear_session("SESSION_ABSOLUTE_TIMEOUT")
        return False
    with db_connection() as conn:
        row = conn.execute("SELECT IsActive FROM auth_users WHERE UserID=?", (auth["user_id"],)).fetchone()
    if not row or not row["IsActive"]:
        clear_session("SESSION_REVOKED")
        return False
    auth["last_activity"] = to_iso(now)
    st.session_state.auth = auth
    return True


def has_permission(permission: str) -> bool:
    if not session_is_valid():
        return False
    permissions = set(st.session_state.auth.get("permissions", []))
    return "*" in permissions or permission in permissions


def current_user() -> dict:
    return dict(st.session_state.get("auth", {}))


def change_own_password(current_password: str, new_password: str) -> None:
    auth = current_user()
    with db_connection() as conn:
        user = conn.execute("SELECT PasswordHash FROM auth_users WHERE UserID=?", (auth["user_id"],)).fetchone()
        if not user or not verify_password(user["PasswordHash"], current_password):
            raise ValueError("Current password is incorrect.")
        if hmac.compare_digest(current_password, new_password):
            raise ValueError("New password must differ from the current password.")
        conn.execute(
            "UPDATE auth_users SET PasswordHash=?, MustChangePassword=0, UpdatedUTC=? WHERE UserID=?",
            (hash_password(new_password), to_iso(utc_now()), auth["user_id"]),
        )
    st.session_state.auth["must_change_password"] = False
    audit("PASSWORD_CHANGED", "User changed own password", auth["user_id"], auth["username"])


def login_screen() -> None:
    initialize_auth_schema()
    bootstrap_admin_from_environment()

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT Username,
                   substr(PasswordHash,1,80) AS HashPreview
            FROM auth_users
            WHERE Username='admin'
            """
        ).fetchone()

    st.write(dict(row))

    st.write("DB:", DB_PATH)
    st.write("PEPPER LENGTH:", len(PEPPER))
  
    st.markdown(
        """
        <style>
        .block-container{max-width:1250px;padding-top:1.2rem;padding-bottom:1.2rem}
        header[data-testid="stHeader"]{background:transparent}
        [data-testid="stAppViewContainer"]{background:radial-gradient(circle at 8% 8%,rgba(20,184,166,.13),transparent 30%),radial-gradient(circle at 92% 90%,rgba(56,189,248,.11),transparent 30%),linear-gradient(145deg,#f8fafc,#eef7f7 50%,#f8fafc)}
        #MainMenu,footer{visibility:hidden}
        .fs-head{text-align:center;margin-bottom:1.35rem}
        .fs-logo{width:70px;height:70px;margin:0 auto .75rem;display:flex;align-items:center;justify-content:center;border-radius:22px;background:linear-gradient(145deg,#0f172a,#164e63 52%,#0f766e);color:#fff;font-size:1.18rem;font-weight:850;box-shadow:0 16px 38px rgba(15,23,42,.23)}
        .fs-kicker{display:inline-block;padding:.32rem .85rem;border:1px solid #c5e8e3;border-radius:999px;background:#ecfdf5;color:#0f766e;font-size:.68rem;font-weight:780;letter-spacing:.12em;text-transform:uppercase}
        .fs-title{margin:.55rem 0 0;color:#0f172a;font-size:3.2rem;font-weight:880;letter-spacing:-.055em;line-height:1}
        .fs-accent{background:linear-gradient(90deg,#0f766e,#0891b2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
        .fs-desc{margin-top:.62rem;color:#334155;font-size:1.18rem;font-weight:700}
        .fs-motto{margin-top:.42rem;color:#0f766e;font-size:.95rem;font-weight:760;letter-spacing:.09em;text-transform:uppercase}
        .fs-line{width:104px;height:3px;margin:.78rem auto 0;border-radius:999px;background:linear-gradient(90deg,#14b8a6,#38bdf8)}
        .hero{min-height:490px;padding:1.7rem;border-radius:25px;background:radial-gradient(circle at 88% 10%,rgba(34,211,238,.30),transparent 30%),radial-gradient(circle at 10% 94%,rgba(45,212,191,.23),transparent 35%),linear-gradient(145deg,#0f172a,#123b4a 46%,#0f766e);box-shadow:0 25px 58px rgba(15,23,42,.24);color:#fff}
        .hero-label{color:#99f6e4;font-size:.69rem;font-weight:780;letter-spacing:.13em;text-transform:uppercase}
        .hero-title{margin:.7rem 0;color:#fff;font-size:2rem;font-weight:800;line-height:1.22}
        .hero-copy{color:#d7eeee;font-size:1rem;line-height:1.62;margin-bottom:1rem}
        .hero-callout{padding:.85rem .95rem;margin-bottom:1rem;border:1px solid rgba(255,255,255,.15);border-radius:14px;background:rgba(255,255,255,.08);color:#f8fafc;font-size:.95rem;line-height:1.5}
        .hero-callout strong{color:#99f6e4}
        .cap{display:flex;gap:.72rem;align-items:flex-start;padding:.66rem .78rem;margin-bottom:.55rem;border:1px solid rgba(255,255,255,.13);border-radius:13px;background:rgba(255,255,255,.075)}
        .cap-num{min-width:35px;height:35px;display:flex;align-items:center;justify-content:center;border-radius:10px;background:rgba(255,255,255,.10);color:#99f6e4;font-size:.72rem;font-weight:820}
        .cap-title{color:#fff;font-size:.96rem;font-weight:760}.cap-text{color:#cbe4e3;font-size:.82rem;line-height:1.4}
        .cap-ai{border-color:rgba(56,189,248,.33);background:linear-gradient(90deg,rgba(8,145,178,.20),rgba(20,184,166,.11))}
        .login-label{color:#0f766e;font-size:.69rem;font-weight:780;letter-spacing:.11em;text-transform:uppercase}
        .login-title{margin:.28rem 0;color:#0f172a;font-size:2.1rem;font-weight:840}
        .login-copy{color:#64748b;font-size:.98rem;line-height:1.55;margin-bottom:1rem}
        div[data-testid="stForm"]{padding:2rem;border:1px solid rgba(203,213,225,.76);border-radius:19px;background:rgba(255,255,255,.94);box-shadow:0 20px 46px rgba(15,23,42,.09)}
        div[data-baseweb="input"]{border-radius:11px} div[data-baseweb="input"] input{min-height:2.72rem}
        .stFormSubmitButton>button{min-height:3rem;border:0;border-radius:11px;background:linear-gradient(90deg,#0f766e,#0891b2);color:#fff;font-weight:750;box-shadow:0 11px 26px rgba(8,145,178,.23)}
        .security{margin-top:1rem;padding:.88rem .95rem;border:1px solid #d7e9e6;border-left:4px solid #14b8a6;border-radius:11px;background:#f0fdfa;color:#52656c;font-size:.76rem;line-height:1.55}
        .support,.fs-footer{text-align:center;color:#71818a;font-size:.73rem;line-height:1.5}.support{margin-top:.75rem}.fs-footer{margin-top:1.35rem}
        @media(max-width:768px){.fs-title{font-size:2.08rem}.hero{min-height:auto;padding:1.4rem}.fs-motto{font-size:.71rem;letter-spacing:.05em}}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="fs-head">
          <div class="fs-logo">360°</div>
          <div class="fs-kicker">Monitoring · Evaluation · Learning</div>
          <h1 class="fs-title">FORESIGHT<span class="fs-accent">360</span></h1>
          <div class="fs-desc">Integrated Monitoring, Forecasting &amp; Decision Intelligence</div>
          <div class="fs-motto">Monitor • Learn • AI Forecast • Decide • Act</div>
          <div class="fs-line"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    information_column, login_column = st.columns([1.1, 0.9], gap="large")

    with information_column:
        st.markdown(
            """
            <div class="hero">
              <div class="hero-label">Evidence into action</div>
              <div class="hero-title">See progress clearly. Anticipate risk. Act earlier.</div>
              <div class="hero-copy">A unified intelligence environment for indicator management, governed workflows, predictive monitoring, organizational learning, and better project decisions.</div>
              <div class="hero-callout"><strong>Move beyond retrospective reporting.</strong><br>Transform monitoring information into foresight, accountability, learning, and actionable project intelligence.</div>
              <div class="cap"><div class="cap-num">01</div><div><div class="cap-title">Centralized ITT Repository</div><div class="cap-text">Organized and accessible indicator records across projects, partners, and reporting periods.</div></div></div>
              <div class="cap"><div class="cap-num">02</div><div><div class="cap-title">Workflow Governance</div><div class="cap-text">Accountable data entry, review, correction, approval, and lifecycle processes.</div></div></div>
              <div class="cap"><div class="cap-num">03</div><div><div class="cap-title">Early Warning Intelligence</div><div class="cap-text">Identify indicators requiring attention before performance risks become critical.</div></div></div>
              <div class="cap"><div class="cap-num">04</div><div><div class="cap-title">Organizational Learning</div><div class="cap-text">Preserve evidence for learning, planning, proposal development, and future project design.</div></div></div>
              <div class="cap cap-ai"><div class="cap-num">AI</div><div><div class="cap-title">AI Forecasting</div><div class="cap-text">Forecast indicator performance, assess target achievement, and support proactive management decisions.</div></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with login_column:
        st.markdown(
            """
            <div class="login-label">Secure intelligence workspace</div>
            <h2 class="login-title">Welcome back</h2>
            <div class="login-copy">Sign in with your authorized account to access role-based dashboards, monitoring workflows, and decision-support services.</div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False, border=True):
            username = st.text_input("Username", placeholder="Enter your username", max_chars=50)
            password = st.text_input("Password", type="password", placeholder="Enter your password", max_chars=128)
            submitted = st.form_submit_button("Access workspace", type="primary", use_container_width=True)
        if submitted:
            if not username.strip() or not password:
                st.warning(
                    "Enter both your username and password."
                )
            else:
                user = authenticate(
                    username,
                    password
                )

               

                if user:
                    establish_session(user)
                    st.rerun()

                st.error(
                    "Sign-in failed. Check your credentials or contact the system administrator."
                )

def _forced_password_change() -> None:
    st.warning("You must change your temporary password before continuing.")
    with st.form("forced_password_change"):
        current_password = st.text_input("Current password", type="password")
        new_password = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Change password", type="primary")
    if submitted:
        if new_password != confirm:
            st.error("New passwords do not match.")
        else:
            try:
                change_own_password(current_password, new_password)
                st.success("Password changed successfully.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.stop()


def require_login(permission: str | None = None) -> dict:
    if not session_is_valid():
        login_screen()
        st.stop()
    if st.session_state.auth.get("must_change_password"):
        _forced_password_change()
    if permission and not has_permission(permission):
        st.error("You do not have permission to access this page.")
        st.stop()
    with st.sidebar:
        st.caption(f"Signed in as **{st.session_state.auth['full_name']}**")
        st.caption("Roles: " + ", ".join(st.session_state.auth.get("roles", [])))
        if st.button("Sign out", key=f"logout_{permission or 'page'}", use_container_width=True):
            clear_session("LOGOUT")
            st.rerun()
    return current_user()

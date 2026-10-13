# Secure Streamlit Authentication Integration

## 1. Install dependency

```powershell
pip install -r requirements-auth.txt
```

## 2. Create the first administrator in PowerShell

Run this only for initial setup. Use your own strong temporary password.

```powershell
$env:APP_BOOTSTRAP_ADMIN_USERNAME="admin"
$env:APP_BOOTSTRAP_ADMIN_FULL_NAME="System Administrator"
$env:APP_BOOTSTRAP_ADMIN_EMAIL="your-email@example.org"
$env:APP_BOOTSTRAP_ADMIN_PASSWORD="Replace-With-A-Strong-Temporary-Password!1"
$env:APP_PASSWORD_PEPPER="Replace-With-A-Long-Random-Secret"
python init_auth.py
```

Keep `APP_PASSWORD_PEPPER` stable. If it changes, existing password hashes cannot be verified. In deployment, store it in protected environment configuration, never in Git.

## 3. Protect the application home file

Add this immediately after imports and before protected content:

```python
from auth import require_login

user = require_login("dashboard.view")
```

Use `require_login()` without a permission if any authenticated user may open the page.

## 4. Protect every Streamlit page

Add one permission guard near the top of each page, after `st.set_page_config(...)` if present:

```python
from auth import require_login
user = require_login("itt.create")
```

Suggested mapping:

```text
ITT data entry:             itt.create
New indicator registration: indicator.register
Review queue:               itt.review
Final approval:             itt.approve
Dataset approval:           dataset.approve
Management dashboards:      dashboard.view
Forecast pages:             forecast.view
Reports:                    report.view
ITT repository:             repository.view
User management:            *
```

## 5. Start the app

```powershell
streamlit run app.py
```

Change `app.py` to your actual Streamlit entry filename.

## Production notes

- Put the app behind HTTPS. Passwords and session traffic must not travel over plain HTTP.
- Do not commit database files, `.streamlit/secrets.toml`, passwords, or the pepper to GitHub.
- The included session uses Streamlit Session State and implements 30-minute inactivity timeout and 8-hour absolute timeout. A hard refresh or new browser tab may create a new Streamlit session and require login again.
- For organization-wide deployment, Microsoft Entra ID through Streamlit OIDC is stronger than maintaining local passwords. Keep this local implementation for controlled deployment, demonstrations, or environments where OIDC is unavailable.

from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys


AUTH_FILE = Path("auth.py")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_FILE = Path(
    f"auth_BEFORE_BALANCED_LAYOUT_{timestamp}.py"
)


def replace_required(
    text: str,
    old: str,
    new: str,
    description: str,
) -> str:
    count = text.count(old)

    if count == 0:
        print(
            f"SKIPPED: {description} "
            f"(the old value was not found)"
        )
        return text

    updated = text.replace(old, new, 1)

    print(
        f"UPDATED: {description}"
    )

    return updated


def restore_backup(message: str) -> None:
    print()
    print(f"ERROR: {message}")

    if BACKUP_FILE.exists():
        shutil.copy2(
            BACKUP_FILE,
            AUTH_FILE,
        )

        print(
            f"RESTORED: {AUTH_FILE} "
            f"from {BACKUP_FILE}"
        )

    raise SystemExit(1)


def main() -> None:
    if not AUTH_FILE.exists():
        raise SystemExit(
            "ERROR: auth.py was not found. "
            "Run this script from the "
            "predictive-monitoring-system folder."
        )

    original_text = AUTH_FILE.read_text(
        encoding="utf-8"
    )

    if "FORESIGHT" not in original_text:
        raise SystemExit(
            "ERROR: FORESIGHT360 design was not found "
            "inside auth.py. No changes were made."
        )

    shutil.copy2(
        AUTH_FILE,
        BACKUP_FILE,
    )

    print(
        f"BACKUP CREATED: {BACKUP_FILE}"
    )

    updated_text = original_text

    # Restore a balanced layout instead of full-screen stretching.
    updated_text = replace_required(
        updated_text,
        "max-width:95vw",
        "max-width:1250px",
        "Balanced page width",
    )

    # Also support the original generated CSS value.
    updated_text = replace_required(
        updated_text,
        "max-width:1160px",
        "max-width:1250px",
        "Original page width",
    )

    # Keep the FORESIGHT360 title large but balanced.
    updated_text = replace_required(
        updated_text,
        "font-size:3.6rem",
        "font-size:3.2rem",
        "Main title size",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:2.7rem",
        "font-size:3.2rem",
        "Original main title size",
    )

    # Increase the platform descriptor.
    updated_text = replace_required(
        updated_text,
        "font-size:1rem;font-weight:670",
        "font-size:1.18rem;font-weight:700",
        "Platform descriptor",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:1.25rem;font-weight:700",
        "font-size:1.18rem;font-weight:700",
        "Large platform descriptor",
    )

    # Increase the motto slightly.
    updated_text = replace_required(
        updated_text,
        "font-size:.82rem",
        "font-size:.95rem",
        "Motto font size",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:1rem",
        "font-size:.95rem",
        "Large motto font size",
    )

    # Make the wording explicitly reference AI forecasting.
    updated_text = replace_required(
        updated_text,
        "Monitor • Learn • Forecast • Decide • Act",
        "Monitor • Learn • AI Forecast • Decide • Act",
        "AI Forecast motto",
    )

    # Increase hero heading while keeping it balanced.
    updated_text = replace_required(
        updated_text,
        "font-size:1.7rem",
        "font-size:2rem",
        "Hero heading",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:2.2rem",
        "font-size:2rem",
        "Large hero heading",
    )

    # Increase hero description.
    updated_text = replace_required(
        updated_text,
        "font-size:.89rem",
        "font-size:1rem",
        "Hero description",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:1.05rem",
        "font-size:1rem",
        "Large hero description",
    )

    # Increase capability titles.
    updated_text = replace_required(
        updated_text,
        "font-size:.83rem;font-weight:730",
        "font-size:.96rem;font-weight:760",
        "Capability titles",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:1rem;font-weight:760",
        "font-size:.96rem;font-weight:760",
        "Large capability titles",
    )

    # Increase capability descriptions.
    updated_text = replace_required(
        updated_text,
        "font-size:.70rem",
        "font-size:.82rem",
        "Capability descriptions",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:.86rem",
        "font-size:.82rem",
        "Large capability descriptions",
    )

    # Keep the login heading readable without making it oversized.
    updated_text = replace_required(
        updated_text,
        "font-size:1.78rem",
        "font-size:2.1rem",
        "Login heading",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:2.5rem",
        "font-size:2.1rem",
        "Large login heading",
    )

    # Increase login description.
    updated_text = replace_required(
        updated_text,
        "font-size:.87rem",
        "font-size:.98rem",
        "Login description",
    )

    updated_text = replace_required(
        updated_text,
        "font-size:1.02rem",
        "font-size:.98rem",
        "Large login description",
    )

    # Use comfortable form padding.
    updated_text = replace_required(
        updated_text,
        "padding:1.45rem",
        "padding:1.7rem",
        "Login form padding",
    )

    updated_text = replace_required(
        updated_text,
        "padding:2rem",
        "padding:1.7rem",
        "Large login form padding",
    )

    AUTH_FILE.write_text(
        updated_text,
        encoding="utf-8",
    )

    try:
        py_compile.compile(
            str(AUTH_FILE),
            doraise=True,
        )
    except py_compile.PyCompileError as error:
        restore_backup(
            f"auth.py failed compilation:\n{error}"
        )

    print()
    print("SUCCESS: Balanced FORESIGHT360 layout applied.")
    print("SUCCESS: auth.py compiled correctly.")
    print(f"Rollback backup: {BACKUP_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print()
        print(f"UNEXPECTED ERROR: {error}")
        sys.exit(1)
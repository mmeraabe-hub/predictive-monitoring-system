import sqlite3

conn = sqlite3.connect("predictive_monitoring.db")

tables = [
    "model_performance",
    "model_registry",
    "itt_upload_batches",
]

for table in tables:
    print("\n" + "=" * 70)
    print(table)
    print("=" * 70)

    exists = conn.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table,)
    ).fetchone()[0]

    if not exists:
        print("TABLE DOES NOT EXIST")
        continue

    columns = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    for column in columns:
        print(column)

conn.close()

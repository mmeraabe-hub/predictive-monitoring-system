import sqlite3


connection = sqlite3.connect(
    "predictive_monitoring.db"
)

connection.execute(
    "PRAGMA foreign_keys = ON"
)

print(
    "Submission staging foreign keys:"
)

foreign_keys = connection.execute(
    """
    PRAGMA foreign_key_list(
        itt_quarterly_submission_staging
    )
    """
).fetchall()

for foreign_key in foreign_keys:
    print(foreign_key)

print("")
print("Indicator master indexes:")

indexes = connection.execute(
    """
    PRAGMA index_list(
        itt_indicator_master
    )
    """
).fetchall()

for index_row in indexes:
    print(index_row)

connection.close()
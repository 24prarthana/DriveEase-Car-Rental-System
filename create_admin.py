


"""Create an admin account for DriveEase."""

import getpass
from werkzeug.security import generate_password_hash
from db import get_connection

print("=== DriveEase Admin Account Setup ===", flush=True)

username = input("New admin username: ").strip()
password = getpass.getpass("New admin password (minimum 10 characters): ")
confirm = getpass.getpass("Confirm password: ")

if not username:
    raise SystemExit("Error: Username cannot be empty.")

if len(password) < 10:
    raise SystemExit("Error: Password must be at least 10 characters.")

if password != confirm:
    raise SystemExit("Error: Passwords do not match.")

connection = get_connection()

try:
    cursor = connection.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM dbo.AdminUsers WHERE Username = ?",
        username
    )

    if cursor.fetchone()[0] > 0:
        raise SystemExit(
            "This username already exists. Choose another username."
        )

    cursor.execute(
        """
        INSERT INTO dbo.AdminUsers
            (Username, PasswordHash, CreatedAt)
        VALUES (?, ?, SYSDATETIME())
        """,
        username,
        generate_password_hash(password)
    )

    connection.commit()
    print("\nSUCCESS! Admin account created.", flush=True)
    print("Open http://127.0.0.1:5000/admin/login to sign in.")

finally:
    connection.close()

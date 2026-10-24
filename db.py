"""SQL Server connection helpers for DriveEase."""
import os
import pyodbc


def get_connection():
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("DB_SERVER", r"PRARTHANA\SQLEXPRESS")
    database = os.getenv("DB_NAME", "CarRentalDB")
    trusted = os.getenv("DB_TRUSTED_CONNECTION", "yes")
    if trusted.lower() in {"yes", "true", "1"}:
        connection_string = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            "Trusted_Connection=yes;TrustServerCertificate=yes;"
        )
    else:
        username = os.getenv("DB_USER", "")
        password = os.getenv("DB_PASSWORD", "")
        connection_string = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"UID={username};PWD={password};TrustServerCertificate=yes;"
        )
    return pyodbc.connect(connection_string, timeout=8)

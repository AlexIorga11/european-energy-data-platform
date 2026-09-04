import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


def get_connection():
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")

    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise ValueError("POSTGRES_PASSWORD is missing from the environment")

    return psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="energy_warehouse",
        user="energy",
        password=password,
        connect_timeout=10,
    )


if __name__ == "__main__":
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            database_name, username = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM staging.energy_prices")
            record_count = cursor.fetchone()[0]

    print(f"Connected to database: {database_name}")
    print(f"Connected as user: {username}")
    print(f"Price records in staging.energy_prices: {record_count}")
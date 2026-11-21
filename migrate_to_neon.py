
import sqlite3
from getpass import getpass
from pathlib import Path

from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.engine import make_url

from models import db


SOURCE_DB = Path(__file__).parent / "instance" / "finance.db"

TABLES = [
    "users",
    "incomes",
    "expenses",
    "budgets",
    "goals"
]


def create_neon_engine():
    raw_url = getpass(
        "Paste your NEW Neon connection string (hidden): "
    )

    # Clean pasted input
    raw_url = raw_url.strip().strip('"').strip("'").strip()

    if not raw_url:
        raise ValueError("Connection string is empty.")

    # Parse connection URL
    url = make_url(raw_url)

    # Use psycopg v3
    if url.drivername in ("postgresql", "postgres"):
        url = url.set(drivername="postgresql+psycopg")

    if url.drivername != "postgresql+psycopg":
        raise ValueError("Invalid PostgreSQL connection URL.")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 15}
    )

    return engine


def main():
    print("=" * 45)
    print("       FINTRACK DATABASE MIGRATION")
    print("=" * 45)

    if not SOURCE_DB.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {SOURCE_DB}"
        )

    neon_engine = None
    sqlite_engine = None

    try:
        # Step 1: Connect to Neon
        neon_engine = create_neon_engine()

        with neon_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        print("\nNeon connection successful!")

        # Step 2: Connect to SQLite
        sqlite_engine = create_engine(
            f"sqlite:///{SOURCE_DB.as_posix()}"
        )

        source_metadata = MetaData()
        source_metadata.reflect(bind=sqlite_engine)

        for table in TABLES:
            if table not in source_metadata.tables:
                raise RuntimeError(
                    f"SQLite table missing: {table}"
                )

        print("Original SQLite database found.")

        # Step 3: Create destination tables
        db.metadata.create_all(neon_engine)

        # Step 4: Check destination tables are empty
        with neon_engine.connect() as conn:
            for table in TABLES:
                count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{table}"')
                ).scalar_one()

                if count > 0:
                    raise RuntimeError(
                        f"Neon table '{table}' already contains "
                        f"{count} records. Migration stopped safely."
                    )

        print("\nNeon tables are empty.")
        print("\nCopying records...\n")

        # Step 5: Copy records in one transaction
        with neon_engine.begin() as target_conn:

            for table_name in TABLES:
                source_table = source_metadata.tables[table_name]
                target_table = db.metadata.tables[table_name]

                copied = 0

                with sqlite_engine.connect() as source_conn:
                    rows = source_conn.execute(
                        source_table.select().order_by(
                            source_table.c.id
                        )
                    ).mappings()

                    while True:
                        batch = rows.fetchmany(100)

                        if not batch:
                            break

                        target_conn.execute(
                            target_table.insert(),
                            [dict(row) for row in batch]
                        )

                        copied += len(batch)

                print(f"{table_name}: {copied} records copied")

            # Step 6: Reset PostgreSQL ID sequences
            for table_name in TABLES:
                target_conn.execute(
                    text("""
                        SELECT setval(
                            pg_get_serial_sequence(
                                :table_name, 'id'
                            ),
                            COALESCE(
                                (SELECT MAX(id)
                                 FROM users_placeholder),
                                1
                            ),
                            true
                        )
                    """.replace(
                        "users_placeholder",
                        f'"{table_name}"'
                    )),
                    {"table_name": table_name}
                )

        # Step 7: Verify all records
        print("\nVERIFYING MIGRATION")
        print("-" * 45)

        all_match = True

        with sqlite3.connect(SOURCE_DB) as source_conn:
            with neon_engine.connect() as target_conn:

                for table_name in TABLES:
                    source_count = source_conn.execute(
                        f'SELECT COUNT(*) FROM "{table_name}"'
                    ).fetchone()[0]

                    target_count = target_conn.execute(
                        text(
                            f'SELECT COUNT(*) FROM "{table_name}"'
                        )
                    ).scalar_one()

                    match = source_count == target_count
                    all_match = all_match and match

                    status = "MATCH" if match else "MISMATCH"

                    print(
                        f"{table_name}: "
                        f"SQLite={source_count}, "
                        f"Neon={target_count} [{status}]"
                    )

        print("-" * 45)

        if all_match:
            print("\nSUCCESS! All records migrated and verified.")
            print("Your original SQLite database is unchanged.")
        else:
            print("\nWARNING: Some record counts do not match.")

    except Exception as error:
        print("\nMIGRATION FAILED")
        print(type(error).__name__, str(error))
        print("\nYour original SQLite database remains unchanged.")

    finally:
        if neon_engine:
            neon_engine.dispose()

        if sqlite_engine:
            sqlite_engine.dispose()


if __name__ == "__main__":
    main()



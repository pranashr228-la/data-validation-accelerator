"""Builds AdventureWorks-shaped sample data for local demo runs.

No live Postgres/Snowflake instances are available for this MVP demo, so
this script generates a small, intentionally-imperfect AdventureWorks
OLTP-like dataset and an AdventureWorks DWH-like dataset, writes them to
Parquet under sample_data/{customer,orders,parquet}/, and loads them into
two local DuckDB files (sample_data/source_oltp.duckdb,
sample_data/target_dwh.duckdb) that the example configs connect to with
``type: duckdb`` in place of ``type: postgres`` / ``type: snowflake``.

Run with: uv run python sample_data/build_sample_data.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

BASE = Path(__file__).parent

# --------------------------------------------------------------------------
# Customer domain (table_to_table example)
# --------------------------------------------------------------------------

# (customer_id, first_name, last_name, email, status, updated_date, balance)
OLTP_CUSTOMERS = [
    (1, "Orlando", "Gee", "orlando0@adventure-works.com", "Active", date(2024, 1, 5), 1250.50),
    (2, "Keith", "Harris", "keith0@adventure-works.com", "Active", date(2024, 1, 6), 340.00),
    (3, "Donna", "Carreras", "donna0@adventure-works.com", "Inactive", date(2024, 1, 7), 0.00),
    (4, "Janet", "Gates", "janet1@adventure-works.com", "Active", date(2024, 1, 8), 980.25),
    (5, "Lucy", "Harrington", "lucy0@adventure-works.com", "Suspended", date(2024, 1, 9), 15.00),
    (6, "Rosmarie", "Carroll", "rosmarie0@adventure-works.com", "Active", date(2024, 1, 9), 500.00),
    (7, "Dominic", "Gash", "dominic0@adventure-works.com", "Active", date(2024, 1, 10), 220.75),
    (8, "Kathleen", "Garza", None, "Active", date(2024, 1, 10), 60.00),  # not_null DQ violation
    (9, "Katherine", "Harding", "katherine0@adventure-works.com", "Active", date(2024, 1, 11), 75.00),
    (10, "Johnny", "Caprio", "johnny0@adventure-works.com", "Unknown", date(2024, 1, 11), 40.00),  # allowed_values violation
    # rows 11-12 exist only in source -> will show up as missing_records in target
    (11, "Christopher", "Beck", "christopher0@adventure-works.com", "Active", date(2024, 1, 12), 300.00),
    (12, "Kim", "Abercrombie", "kim0@adventure-works.com", "Active", date(2024, 1, 12), 150.00),
]

# Target has: row 6 balance drifted (hash+aggregate mismatch), row 9 duplicated
# (duplicate_keys violation), rows 11-12 missing, row 13 extra-only-in-target.
DWH_CUSTOMERS = [
    (1, "Orlando Gee", "orlando0@adventure-works.com", "Active", date(2024, 1, 5), 1250.50, "B001"),
    (2, "Keith Harris", "keith0@adventure-works.com", "Active", date(2024, 1, 6), 340.00, "B001"),
    (3, "Donna Carreras", "donna0@adventure-works.com", "Inactive", date(2024, 1, 7), 0.00, "B001"),
    (4, "Janet Gates", "janet1@adventure-works.com", "Active", date(2024, 1, 8), 980.25, "B001"),
    (5, "Lucy Harrington", "lucy0@adventure-works.com", "Suspended", date(2024, 1, 9), 15.00, "B001"),
    (6, "Rosmarie Carroll", "rosmarie0@adventure-works.com", "Active", date(2024, 1, 9), 550.00, "B001"),  # drifted balance
    (7, "Dominic Gash", "dominic0@adventure-works.com", "Active", date(2024, 1, 10), 220.75, "B001"),
    (8, "Kathleen Garza", None, "Active", date(2024, 1, 10), 60.00, "B001"),
    (9, "Katherine Harding", "katherine0@adventure-works.com", "Active", date(2024, 1, 11), 75.00, "B001"),
    (9, "Katherine Harding", "katherine0@adventure-works.com", "Active", date(2024, 1, 11), 75.00, "B002"),  # duplicate key
    (10, "Johnny Caprio", "johnny0@adventure-works.com", "Unknown", date(2024, 1, 11), 40.00, "B001"),
    (13, "Extra Person", "extra0@adventure-works.com", "Active", date(2024, 1, 13), 90.00, "B001"),  # extra-only-in-target
]


def _write_parquet(rows: list[tuple], names: list[str], path: Path) -> None:
    columns = list(zip(*rows))
    table = pa.table({name: pa.array(col) for name, col in zip(names, columns)})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def build_customer_domain() -> None:
    _write_parquet(
        OLTP_CUSTOMERS,
        ["customer_id", "first_name", "last_name", "email", "status", "updated_date", "balance"],
        BASE / "customer" / "oltp_customer.parquet",
    )
    _write_parquet(
        DWH_CUSTOMERS,
        ["CUSTOMER_ID", "CUSTOMER_NAME", "EMAIL", "STATUS", "UPDATED_DATE", "BALANCE", "LOAD_BATCH_ID"],
        BASE / "customer" / "dwh_dim_customer.parquet",
    )


# --------------------------------------------------------------------------
# Orders domain (query_to_query example: order -> customer -> person chain)
# --------------------------------------------------------------------------

PERSONS = [
    (100, "PK-100", "Orlando", "Gee"),
    (101, "PK-101", "Keith", "Harris"),
    (102, "PK-102", "Donna", "Carreras"),
    (103, "PK-103", "Janet", "Gates"),
]

ORDER_CUSTOMERS = [  # (customer_id, person_id)
    (1, 100),
    (2, 101),
    (3, 102),
    (4, 103),
]

SRC_ORDERS = [
    (5001, 1, 199.99, date(2024, 2, 1), "BATCH01"),
    (5002, 2, 49.50, date(2024, 2, 1), "BATCH01"),
    (5003, 3, 899.00, date(2024, 2, 2), "BATCH01"),
    (5004, 4, 25.00, date(2024, 2, 2), "BATCH01"),
    (5005, 1, 310.10, date(2024, 2, 3), "BATCH01"),  # missing from target
]

FACT_ORDER = [
    (5001, "PK-100", 199.99, date(2024, 2, 1), "BATCH01"),
    (5002, "PK-101", 55.00, date(2024, 2, 1), "BATCH01"),  # amount drifted
    (5003, "PK-102", 899.00, date(2024, 2, 2), "BATCH01"),
    (5004, "PK-103", 25.00, date(2024, 2, 2), "BATCH01"),
]


def build_orders_domain() -> None:
    _write_parquet(
        PERSONS, ["person_id", "person_key", "first_name", "last_name"],
        BASE / "orders" / "oltp_person.parquet",
    )
    _write_parquet(
        ORDER_CUSTOMERS, ["customer_id", "person_id"], BASE / "orders" / "oltp_order_customer.parquet"
    )
    _write_parquet(
        SRC_ORDERS, ["order_id", "customer_id", "order_amount", "order_date", "batch_id"],
        BASE / "orders" / "oltp_order.parquet",
    )
    _write_parquet(
        FACT_ORDER, ["ORDER_ID", "PERSON_KEY", "ORDER_AMOUNT", "ORDER_DATE", "BATCH_ID"],
        BASE / "orders" / "dwh_fact_order.parquet",
    )


# --------------------------------------------------------------------------
# Load everything into two local DuckDB files standing in for Postgres/Snowflake
# --------------------------------------------------------------------------


def build_duckdb_databases() -> None:
    source_db = BASE / "source_oltp.duckdb"
    target_db = BASE / "target_dwh.duckdb"
    source_db.unlink(missing_ok=True)
    target_db.unlink(missing_ok=True)

    with duckdb.connect(str(source_db)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS public")
        con.execute(
            f"CREATE TABLE public.customer AS SELECT * FROM read_parquet("
            f"'{(BASE / 'customer' / 'oltp_customer.parquet').as_posix()}')"
        )
        con.execute(
            f"CREATE TABLE public.person AS SELECT * FROM read_parquet("
            f"'{(BASE / 'orders' / 'oltp_person.parquet').as_posix()}')"
        )
        con.execute(
            f"CREATE TABLE public.order_customer AS SELECT * FROM read_parquet("
            f"'{(BASE / 'orders' / 'oltp_order_customer.parquet').as_posix()}')"
        )
        con.execute(
            f"CREATE TABLE public.src_order AS SELECT * FROM read_parquet("
            f"'{(BASE / 'orders' / 'oltp_order.parquet').as_posix()}')"
        )

    with duckdb.connect(str(target_db)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS curated")
        con.execute(
            f"CREATE TABLE curated.dim_customer AS SELECT * FROM read_parquet("
            f"'{(BASE / 'customer' / 'dwh_dim_customer.parquet').as_posix()}')"
        )
        con.execute(
            f"CREATE TABLE curated.fact_order AS SELECT * FROM read_parquet("
            f"'{(BASE / 'orders' / 'dwh_fact_order.parquet').as_posix()}')"
        )

    # Also drop a couple of plain parquet-to-parquet files for the parquet
    # connector example (same shape on both sides, one dropped row on the
    # target to demonstrate a missing_records finding).
    parquet_dir = BASE / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(
        PERSONS, ["person_id", "person_key", "first_name", "last_name"],
        parquet_dir / "person_source.parquet",
    )
    _write_parquet(
        PERSONS[:-1], ["person_id", "person_key", "first_name", "last_name"],
        parquet_dir / "person_target.parquet",
    )


if __name__ == "__main__":
    build_customer_domain()
    build_orders_domain()
    build_duckdb_databases()
    print("Sample data built under sample_data/")

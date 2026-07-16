"""Register the DVA Postgres database and dashboard SQL datasets in Superset."""

from __future__ import annotations

import os
import time

from sqlalchemy import create_engine, text


def wait_for_db(url: str, retries: int = 30, delay: float = 2.0) -> None:
    engine = create_engine(url)
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def main() -> None:
    superset_url = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql+psycopg2://dva:dva@postgres:5432/superset",
    )
    dva_url = os.environ.get("DVA_DATABASE_URL", "postgresql://dva:dva@postgres:5432/dva")

    wait_for_db(superset_url)
    wait_for_db(dva_url)

    # Superset metadata tables are managed by `superset db upgrade`.
    # Dataset and dashboard creation is done via exported assets in
    # superset/dashboards/ and documented import steps in docs/dashboards.md.
    # This bootstrap verifies connectivity only.
    engine = create_engine(dva_url.replace("postgresql://", "postgresql+psycopg2://"))
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM dva.run_summary")).scalar()
        print(f"DVA results database reachable ({count or 0} runs in dva.run_summary)")


if __name__ == "__main__":
    main()

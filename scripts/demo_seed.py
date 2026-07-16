#!/usr/bin/env python3
"""Run multiple validation configs to populate trend dashboards."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CONFIGS = [
    "configs/examples/postgres_to_snowflake_table.yaml",
    "configs/examples/query_to_query_fact_order.yaml",
    "configs/examples/parquet_to_parquet.yaml",
    "configs/examples/schema_contract_customer.yaml",
]


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for i in range(runs):
        for config in CONFIGS:
            rel = REPO_ROOT / config
            print(f"\n=== Demo run {i + 1}/{runs}: {config} ===")
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "dva",
                    "run",
                    "--config",
                    str(rel),
                    "--allow-validation-fail",
                ],
                cwd=REPO_ROOT,
            )
            if result.returncode != 0:
                return result.returncode
    print(f"\nSeeded {runs * len(CONFIGS)} validation runs for dashboard trends.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

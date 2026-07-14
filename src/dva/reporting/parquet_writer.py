"""Write lists of pydantic report models out to Parquet files."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel


def write_models_to_parquet(path: Path, models: list[BaseModel]) -> None:
    """Write ``models`` to ``path`` as Parquet. No-op if the list is empty."""
    if not models:
        return
    rows = [m.model_dump() for m in models]
    table = pa.Table.from_pylist(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)

"""Run manifest writer — manifest.json summarizing a validation run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))

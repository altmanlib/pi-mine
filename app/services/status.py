"""Inspect extract/mine artifacts under the output directory."""

from pathlib import Path
from typing import Any

TRACKED_FILES = (
    ("utterances", "utterances.jsonl"),
    ("candidates_md", "candidates.md"),
    ("candidates_json", "candidates.json"),
    ("persona", "persona.md"),
)


def collect_status(out_dir: Path) -> dict[str, Any]:
    """Return presence and sizes for known pipeline outputs."""
    files: dict[str, dict[str, Any]] = {}
    for key, name in TRACKED_FILES:
        path = out_dir / name
        if path.is_file():
            files[key] = {
                "path": str(path),
                "exists": True,
                "size": path.stat().st_size,
            }
        else:
            files[key] = {
                "path": str(path),
                "exists": False,
                "size": 0,
            }
    return {
        "out_dir": str(out_dir),
        "out_dir_exists": out_dir.is_dir(),
        "files": files,
    }

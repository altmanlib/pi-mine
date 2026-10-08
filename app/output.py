"""CLI output helpers: human text by default, JSON when requested."""

import json
import sys
from typing import Any


def output_json(data: Any) -> None:
    """Write JSON to stdout."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_lines(lines: list[str]) -> None:
    """Write plain human-readable lines to stdout."""
    for line in lines:
        print(line)


def print_error(message: str) -> None:
    """Write an error to stderr."""
    print(message, file=sys.stderr)

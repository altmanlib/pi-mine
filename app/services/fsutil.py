"""Filesystem helpers shared by pipeline stages."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, TextIO


@contextmanager
def _atomic_replace(path: Path) -> Iterator[Path]:
    """Yield ``<path>.tmp`` and move it over ``path`` only when the block succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        yield tmp_path
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


@contextmanager
def atomic_text_writer(path: Path) -> Iterator[TextIO]:
    """Write UTF-8 text atomically."""
    with _atomic_replace(path) as tmp_path, tmp_path.open("w", encoding="utf-8") as handle:
        yield handle


@contextmanager
def atomic_binary_writer(path: Path) -> Iterator[BinaryIO]:
    """Write bytes atomically."""
    with _atomic_replace(path) as tmp_path, tmp_path.open("wb") as handle:
        yield handle

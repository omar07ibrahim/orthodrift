"""Durable local text I/O helpers."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, overwrite: bool = True) -> None:
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be boolean")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
            temporary.unlink()
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_lf_records(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    if not text:
        return ()
    records = text.split("\n")
    if records[-1] == "":
        records.pop()
    return tuple(records)

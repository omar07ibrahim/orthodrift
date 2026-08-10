"""Durable local text I/O helpers."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

MAX_CASE_BYTES = 1_048_576
MAX_ARTIFACT_BYTES = 16_777_216
MAX_ARTIFACT_RECORDS = 1_000


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


def read_text_limited(path: Path, *, max_bytes: int) -> str:
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    with path.open("rb") as handle:
        payload = handle.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f"{path} exceeds {max_bytes} bytes")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{path} is not valid UTF-8") from error


def read_lf_records(
    path: Path,
    *,
    max_bytes: int = MAX_ARTIFACT_BYTES,
    max_records: int = MAX_ARTIFACT_RECORDS,
) -> tuple[str, ...]:
    if type(max_records) is not int or max_records <= 0:
        raise ValueError("max_records must be a positive integer")
    text = read_text_limited(path, max_bytes=max_bytes)
    if not text:
        return ()
    records = text.split("\n")
    if records[-1] == "":
        records.pop()
    if len(records) > max_records:
        raise ValueError(f"{path} exceeds {max_records} records")
    return tuple(records)

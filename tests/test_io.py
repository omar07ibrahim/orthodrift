import os
from pathlib import Path

import pytest

from orthodrift import _io


def test_atomic_write_preserves_existing_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "evidence.jsonl"
    target.write_text("previous\n", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(f"cannot replace {source} with {destination}")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="cannot replace"):
        _io.atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "previous\n"
    assert not tuple(tmp_path.glob(".*.tmp"))


def test_no_clobber_publish_is_safe_when_a_competitor_wins_the_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "evidence.jsonl"
    real_link = os.link

    def competing_link(source: Path, destination: Path) -> None:
        Path(destination).write_text("competitor\n", encoding="utf-8")
        real_link(source, destination)

    monkeypatch.setattr(os, "link", competing_link)

    with pytest.raises(FileExistsError):
        _io.atomic_write_text(target, "ours\n", overwrite=False)

    assert target.read_text(encoding="utf-8") == "competitor\n"
    assert not tuple(tmp_path.glob(".*.tmp"))


def test_no_clobber_publish_preserves_a_dangling_symlink(tmp_path: Path) -> None:
    target = tmp_path / "evidence.jsonl"
    target.symlink_to(tmp_path / "missing.jsonl")

    with pytest.raises(FileExistsError):
        _io.atomic_write_text(target, "ours\n", overwrite=False)

    assert target.is_symlink()
    assert target.readlink() == tmp_path / "missing.jsonl"

def test_bounded_reader_rejects_oversized_and_invalid_utf8(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"12345")
    with pytest.raises(ValueError, match="exceeds 4 bytes"):
        _io.read_text_limited(oversized, max_bytes=4)

    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"\\xff")
    with pytest.raises(ValueError, match="not valid UTF-8"):
        _io.read_text_limited(invalid, max_bytes=4)


def test_record_reader_bounds_record_count(tmp_path: Path) -> None:
    artifact = tmp_path / "many.jsonl"
    artifact.write_text("{}\\n{}\\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exceeds 1 records"):
        _io.read_lf_records(artifact, max_records=1)

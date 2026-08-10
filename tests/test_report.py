from dataclasses import replace
from pathlib import Path

import pytest

from orthodrift.cli import main
from orthodrift.experiment import load_case, run_case
from orthodrift.report import render_report, write_report
from orthodrift.run_serialization import write_runs_jsonl

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "shaki-rank-flip.json"


def test_report_is_derived_from_a_verified_run() -> None:
    run = run_case(load_case(EXAMPLE))

    rendered = render_report(run)

    assert "shaki-decomposed-grapheme" in rendered
    assert "One grapheme" in rendered
    assert "U+015E → U+0053 U+0327" in rendered
    assert '"rank":1' in rendered
    assert '"rank":2' in rendered
    assert run.runtime.engine_sha256 in rendered
    assert ".hero-grid > * { min-width: 0; }" in rendered
    assert "overflow-wrap: anywhere" in rendered
    assert "https://" not in rendered


def test_report_escapes_experiment_text_in_markup_and_json() -> None:
    case = replace(load_case(EXAMPLE), name="case <script>alert")
    changed = run_case(case)

    rendered = render_report(changed)

    assert "<title>case <script>alert" not in rendered
    assert "<title>case &lt;script&gt;alert" in rendered
    assert "\\u003cscript>alert" in rendered
    assert changed.runtime.engine_sha256 in rendered


def test_report_write_is_no_clobber_by_default(tmp_path: Path) -> None:
    run = run_case(load_case(EXAMPLE))
    target = tmp_path / "report.html"
    target.write_text("sentinel", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_report(target, run)

    assert target.read_text(encoding="utf-8") == "sentinel"


def test_report_cli_writes_and_rejects_multiple_runs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = run_case(load_case(EXAMPLE))
    artifact = tmp_path / "run.jsonl"
    report = tmp_path / "report.html"
    write_runs_jsonl(artifact, [run])

    assert main(["report", str(artifact), "--output", str(report)]) == 0
    assert report.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert f"report: {report}" in capsys.readouterr().out

    write_runs_jsonl(artifact, [run, run])
    assert main(["report", str(artifact), "--output", str(report), "--force"]) == 1
    assert "exactly one experiment run" in capsys.readouterr().err

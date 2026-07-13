from dataclasses import replace
from pathlib import Path

import pytest

from orthodrift.cli import _reduction_summary, main
from orthodrift.experiment import load_case, run_case
from orthodrift.reduction import Minimality
from orthodrift.run_serialization import dumps_run, read_runs_jsonl

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "shaki-rank-flip.json"


def test_cli_runs_case_and_writes_replayable_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "nested" / "evidence.jsonl"

    exit_code = main(["run", str(EXAMPLE), "--output", str(output)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "case: shaki-decomposed-grapheme",
        "baseline rank: 1",
        "full mutant rank: 2",
        "global minimum: 1/3 edits",
        "edit 0 [0:1]: U+015E -> U+0053 U+0327",
        f"evidence: {output}",
    ]
    assert read_runs_jsonl(output)[0].reduction.reduced_indexes == (0,)

    assert main(["verify", str(output)]) == 0
    assert capsys.readouterr().out == "verified: 1 experiment run(s)\n"


def test_cli_refuses_to_overwrite_its_input_case(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = EXAMPLE.read_bytes()

    exit_code = main(["run", str(EXAMPLE), "--output", str(EXAMPLE)])

    assert exit_code == 1
    assert "must not overwrite" in capsys.readouterr().err
    assert EXAMPLE.read_bytes() == original


def test_cli_requires_force_to_replace_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "evidence.jsonl"
    output.write_text("keep me", encoding="utf-8")

    assert main(["run", str(EXAMPLE), "--output", str(output)]) == 1
    assert "pass --force" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "keep me"

    assert main(["run", str(EXAMPLE), "--output", str(output), "--force"]) == 0
    capsys.readouterr()
    assert read_runs_jsonl(output)[0].case.name == "shaki-decomposed-grapheme"


def test_cli_reports_huge_json_numbers_without_a_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    encoded = dumps_run(run_case(load_case(EXAMPLE)))
    huge = "1" + "0" * 1_000
    artifact = tmp_path / "huge-number.jsonl"
    artifact.write_text(encoded.replace('"k1":1.2', f'"k1":{huge}') + "\n", encoding="utf-8")

    assert main(["verify", str(artifact)]) == 1
    error = capsys.readouterr().err
    assert "finite number" in error
    assert "Traceback" not in error


def test_cli_reports_deep_json_without_a_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = tmp_path / "deep.json"
    case.write_text('{"nested":' + "[" * 1_100 + "0" + "]" * 1_100 + "}", encoding="utf-8")

    assert main(["run", str(case)]) == 1
    error = capsys.readouterr().err
    assert "nesting" in error
    assert "Traceback" not in error


def test_cli_does_not_overclaim_one_minimal_reduction() -> None:
    run = run_case(load_case(EXAMPLE))
    local_reduction = replace(run.reduction, minimality=Minimality.ONE_MINIMAL)
    local_run = replace(run, reduction=local_reduction)

    assert _reduction_summary(local_run) == "one-minimal counterexample: 1/3 edits"

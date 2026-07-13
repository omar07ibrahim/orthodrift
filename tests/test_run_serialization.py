import json
from dataclasses import replace
from pathlib import Path

import pytest

from orthodrift.experiment import RetrievalCaseRun, load_case, run_case
from orthodrift.run_serialization import (
    RUN_SCHEMA_VERSION,
    dumps_run,
    loads_run,
    read_runs_jsonl,
    run_from_record,
    run_to_record,
    verify_run,
    write_runs_jsonl,
)

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "shaki-rank-flip.json"


def _run() -> RetrievalCaseRun:
    return run_case(load_case(EXAMPLE))


def test_experiment_run_round_trips_and_replays() -> None:
    run = _run()

    encoded = dumps_run(run)
    decoded = loads_run(encoded)

    assert decoded == run
    assert json.loads(encoded)["schema"] == RUN_SCHEMA_VERSION
    assert "Şəki atlası sənətkarlıq" in encoded
    assert decoded.runtime.engine_sha256
    assert decoded.retriever.tokenizer_pattern
    verify_run(decoded)


def test_jsonl_write_is_readable_and_verified(tmp_path: Path) -> None:
    run = _run()
    path = tmp_path / "run.jsonl"

    write_runs_jsonl(path, [run])

    assert path.read_text(encoding="utf-8").endswith("\n")
    assert read_runs_jsonl(path) == (run,)
    assert not tuple(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
def test_jsonl_preserves_unicode_line_separators(tmp_path: Path, separator: str) -> None:
    run = _run()
    first_document = replace(
        run.case.documents[0],
        text=f"{run.case.documents[0].text}{separator}",
    )
    case = replace(run.case, documents=(first_document, *run.case.documents[1:]))
    changed = run_case(case)
    path = tmp_path / "unicode-separator.jsonl"

    write_runs_jsonl(path, [changed])

    assert read_runs_jsonl(path) == (changed,)


def test_embedded_case_digest_detects_tampering() -> None:
    record = run_to_record(_run())
    case = record["case"]
    assert isinstance(case, dict)
    case["query"] = "tampered"

    with pytest.raises(ValueError, match="case_sha256"):
        run_from_record(record)


def test_rank_measurements_cannot_disagree_with_failure_flags() -> None:
    record = run_to_record(_run())
    measurements = record["measurements"]
    assert isinstance(measurements, list)
    baseline = measurements[0]
    assert isinstance(baseline, dict)
    baseline["target_rank"] = None

    with pytest.raises(ValueError, match="failure flag"):
        run_from_record(record)


def test_rank_measurements_cannot_exceed_the_corpus_size() -> None:
    record = run_to_record(_run())
    measurements = record["measurements"]
    assert isinstance(measurements, list)
    full = measurements[1]
    assert isinstance(full, dict)
    full["target_rank"] = 999

    with pytest.raises(ValueError, match="corpus size"):
        run_from_record(record)


def test_replay_rejects_forged_minimality_and_runtime() -> None:
    record = run_to_record(_run())
    reduction = record["reduction"]
    assert isinstance(reduction, dict)
    reduction["minimality"] = "one-minimal"
    forged = run_from_record(record)
    with pytest.raises(ValueError, match="reduction does not match"):
        verify_run(forged)

    record = run_to_record(_run())
    runtime = record["runtime"]
    assert isinstance(runtime, dict)
    runtime["engine_sha256"] = "0" * 64
    incompatible = run_from_record(record)
    with pytest.raises(ValueError, match="runtime fingerprint"):
        verify_run(incompatible)


def test_duplicate_run_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate JSON field"):
        loads_run(f'{{"schema":"{RUN_SCHEMA_VERSION}","schema":"{RUN_SCHEMA_VERSION}"}}')

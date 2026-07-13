"""Self-contained, replayable retrieval-run artifacts."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from pathlib import Path

from orthodrift._io import atomic_write_text, read_lf_records
from orthodrift._schema import (
    array,
    boolean,
    canonical_dumps,
    integer,
    loads_mapping,
    mapping,
    nullable_integer,
    number,
    require_keys,
    string,
)
from orthodrift.experiment import (
    RankMeasurement,
    RetrievalCaseRun,
    RuntimeFingerprint,
    case_from_record,
    case_to_record,
    run_case,
)
from orthodrift.retrieval import BM25Spec
from orthodrift.serialization import result_from_record, result_to_record

RUN_SCHEMA_VERSION = "orthodrift.experiment-run.v1"


def run_to_record(run: RetrievalCaseRun) -> dict[str, object]:
    case_record = case_to_record(run.case)
    return {
        "schema": RUN_SCHEMA_VERSION,
        "case": case_record,
        "case_sha256": _record_digest(case_record),
        "retriever": _retriever_to_record(run.retriever),
        "runtime": _runtime_to_record(run.runtime),
        "measurements": [
            {
                "edit_indexes": list(measurement.edit_indexes),
                "target_rank": measurement.target_rank,
            }
            for measurement in run.measurements
        ],
        "reduction": result_to_record(run.reduction),
    }


def run_from_record(record: Mapping[str, object]) -> RetrievalCaseRun:
    require_keys(
        record,
        {
            "schema",
            "case",
            "case_sha256",
            "retriever",
            "runtime",
            "measurements",
            "reduction",
        },
        "experiment run",
    )
    schema = string(record["schema"], "schema")
    if schema != RUN_SCHEMA_VERSION:
        raise ValueError(f"unsupported experiment-run schema: {schema!r}")

    case_record = mapping(record["case"], "case")
    recorded_digest = string(record["case_sha256"], "case_sha256")
    actual_digest = _record_digest(case_record)
    if recorded_digest != actual_digest:
        raise ValueError("case_sha256 does not match the embedded case")

    return RetrievalCaseRun(
        case=case_from_record(case_record),
        retriever=_retriever_from_record(mapping(record["retriever"], "retriever")),
        runtime=_runtime_from_record(mapping(record["runtime"], "runtime")),
        measurements=tuple(
            _measurement_from_record(mapping(item, "measurements item"))
            for item in array(record["measurements"], "measurements")
        ),
        reduction=result_from_record(mapping(record["reduction"], "reduction")),
    )


def verify_run(run: RetrievalCaseRun) -> None:
    current_runtime = RuntimeFingerprint.capture()
    if run.runtime != current_runtime:
        raise ValueError(
            "runtime fingerprint does not match; replay with the recorded "
            "OrthoDrift, Python, Unicode, and regex versions"
        )

    replayed = run_case(run.case, run.retriever)
    if replayed.measurements != run.measurements:
        raise ValueError("recorded target ranks do not match a deterministic replay")
    if replayed.reduction != run.reduction:
        raise ValueError("recorded reduction does not match a deterministic replay")


def dumps_run(run: RetrievalCaseRun) -> str:
    return canonical_dumps(run_to_record(run))


def loads_run(line: str) -> RetrievalCaseRun:
    return run_from_record(loads_mapping(line, "experiment run"))


def write_runs_jsonl(
    path: Path,
    runs: Iterable[RetrievalCaseRun],
    *,
    overwrite: bool = True,
) -> None:
    lines = [dumps_run(run) for run in runs]
    text = "\n".join(lines) + ("\n" if lines else "")
    atomic_write_text(path, text, overwrite=overwrite)


def read_runs_jsonl(path: Path) -> tuple[RetrievalCaseRun, ...]:
    runs: list[RetrievalCaseRun] = []
    for line_number, line in enumerate(read_lf_records(path), start=1):
        if not line:
            raise ValueError(f"blank JSONL record at line {line_number}")
        try:
            runs.append(loads_run(line))
        except ValueError as error:
            raise ValueError(f"invalid experiment run at line {line_number}: {error}") from error
    return tuple(runs)


def _retriever_to_record(spec: BM25Spec) -> dict[str, object]:
    return {
        "implementation": spec.implementation,
        "k1": spec.k1,
        "b": spec.b,
        "tie_break": spec.tie_break,
        "tokenizer": {
            "implementation": spec.tokenizer,
            "pattern": spec.tokenizer_pattern,
            "casefold": spec.casefold,
        },
    }


def _retriever_from_record(record: Mapping[str, object]) -> BM25Spec:
    require_keys(record, {"implementation", "k1", "b", "tie_break", "tokenizer"}, "retriever")
    tokenizer = mapping(record["tokenizer"], "retriever.tokenizer")
    require_keys(
        tokenizer,
        {"implementation", "pattern", "casefold"},
        "retriever.tokenizer",
    )
    return BM25Spec(
        implementation=string(record["implementation"], "retriever.implementation"),
        k1=number(record["k1"], "retriever.k1"),
        b=number(record["b"], "retriever.b"),
        tie_break=string(record["tie_break"], "retriever.tie_break"),
        tokenizer=string(tokenizer["implementation"], "retriever.tokenizer.implementation"),
        tokenizer_pattern=string(tokenizer["pattern"], "retriever.tokenizer.pattern"),
        casefold=boolean(tokenizer["casefold"], "retriever.tokenizer.casefold"),
    )


def _runtime_to_record(runtime: RuntimeFingerprint) -> dict[str, object]:
    return {
        "orthodrift_version": runtime.orthodrift_version,
        "engine_sha256": runtime.engine_sha256,
        "python_implementation": runtime.python_implementation,
        "python_version": runtime.python_version,
        "python_unicode_version": runtime.python_unicode_version,
        "regex_version": runtime.regex_version,
    }


def _runtime_from_record(record: Mapping[str, object]) -> RuntimeFingerprint:
    require_keys(
        record,
        {
            "orthodrift_version",
            "engine_sha256",
            "python_implementation",
            "python_version",
            "python_unicode_version",
            "regex_version",
        },
        "runtime",
    )
    return RuntimeFingerprint(
        orthodrift_version=string(record["orthodrift_version"], "runtime.orthodrift_version"),
        engine_sha256=string(record["engine_sha256"], "runtime.engine_sha256"),
        python_implementation=string(
            record["python_implementation"], "runtime.python_implementation"
        ),
        python_version=string(record["python_version"], "runtime.python_version"),
        python_unicode_version=string(
            record["python_unicode_version"], "runtime.python_unicode_version"
        ),
        regex_version=string(record["regex_version"], "runtime.regex_version"),
    )


def _measurement_from_record(record: Mapping[str, object]) -> RankMeasurement:
    require_keys(record, {"edit_indexes", "target_rank"}, "measurement")
    return RankMeasurement(
        edit_indexes=tuple(
            _measurement_index(value)
            for value in array(record["edit_indexes"], "measurement.edit_indexes")
        ),
        target_rank=nullable_integer(record["target_rank"], "measurement.target_rank"),
    )


def _measurement_index(value: object) -> int:
    return integer(value, "measurement.edit_indexes item")


def _record_digest(record: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_dumps(record).encode("utf-8")).hexdigest()

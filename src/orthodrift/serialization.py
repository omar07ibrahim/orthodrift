"""Versioned JSONL evidence for reduction runs."""

from __future__ import annotations

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
    require_keys,
    string,
)
from orthodrift.reduction import (
    Minimality,
    ReductionResult,
    ReductionTrial,
)
from orthodrift.text import GraphemeEdit

SCHEMA_VERSION = "orthodrift.reduction.v1"


def result_to_record(result: ReductionResult) -> dict[str, object]:
    return {
        "schema": SCHEMA_VERSION,
        "source": result.source,
        "original_edits": [_edit_to_record(edit) for edit in result.original_edits],
        "reduced_indexes": list(result.reduced_indexes),
        "text": result.text,
        "minimality": result.minimality.value,
        "trials": [
            {
                "edit_indexes": list(trial.edit_indexes),
                "text": trial.text,
                "failed": trial.failed,
            }
            for trial in result.trials
        ],
    }


def result_from_record(record: Mapping[str, object]) -> ReductionResult:
    require_keys(
        record,
        {
            "schema",
            "source",
            "original_edits",
            "reduced_indexes",
            "text",
            "minimality",
            "trials",
        },
        "result",
    )
    schema = string(record["schema"], "schema")
    if schema != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema: {schema!r}")

    edits = tuple(
        _edit_from_record(mapping(item, "original_edits item"))
        for item in array(record["original_edits"], "original_edits")
    )
    reduced_indexes = tuple(
        integer(item, "reduced_indexes item")
        for item in array(record["reduced_indexes"], "reduced_indexes")
    )
    if any(index < 0 or index >= len(edits) for index in reduced_indexes):
        raise ValueError("reduced index is outside original_edits")
    trials = tuple(
        _trial_from_record(mapping(item, "trials item"))
        for item in array(record["trials"], "trials")
    )

    try:
        minimality = Minimality(string(record["minimality"], "minimality"))
    except ValueError as error:
        raise ValueError(f"invalid minimality: {record['minimality']!r}") from error

    return ReductionResult(
        source=string(record["source"], "source"),
        original_edits=edits,
        reduced_indexes=reduced_indexes,
        reduced_edits=tuple(edits[index] for index in reduced_indexes),
        text=string(record["text"], "text"),
        minimality=minimality,
        trials=trials,
    )


def dumps_result(result: ReductionResult) -> str:
    return canonical_dumps(result_to_record(result))


def loads_result(line: str) -> ReductionResult:
    return result_from_record(loads_mapping(line, "reduction"))


def write_jsonl(path: Path, results: Iterable[ReductionResult]) -> None:
    lines = [dumps_result(result) for result in results]
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def read_jsonl(path: Path) -> tuple[ReductionResult, ...]:
    results: list[ReductionResult] = []
    for line_number, line in enumerate(read_lf_records(path), start=1):
        if not line:
            raise ValueError(f"blank JSONL record at line {line_number}")
        try:
            results.append(loads_result(line))
        except ValueError as error:
            raise ValueError(f"invalid reduction record at line {line_number}: {error}") from error
    return tuple(results)


def _edit_to_record(edit: GraphemeEdit) -> dict[str, object]:
    return {
        "start": edit.start,
        "before": list(edit.before),
        "after": list(edit.after),
    }


def _edit_from_record(record: Mapping[str, object]) -> GraphemeEdit:
    require_keys(record, {"start", "before", "after"}, "edit")
    return GraphemeEdit(
        start=integer(record["start"], "edit.start"),
        before=tuple(
            string(item, "edit.before item") for item in array(record["before"], "edit.before")
        ),
        after=tuple(
            string(item, "edit.after item") for item in array(record["after"], "edit.after")
        ),
    )


def _trial_from_record(record: Mapping[str, object]) -> ReductionTrial:
    require_keys(record, {"edit_indexes", "text", "failed"}, "trial")
    return ReductionTrial(
        edit_indexes=tuple(
            integer(item, "trial.edit_indexes item")
            for item in array(record["edit_indexes"], "trial.edit_indexes")
        ),
        text=string(record["text"], "trial.text"),
        failed=boolean(record["failed"], "trial.failed"),
    )

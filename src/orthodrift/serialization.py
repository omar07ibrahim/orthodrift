"""Versioned JSONL evidence for reduction runs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

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
    _require_keys(
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
    schema = _string(record["schema"], "schema")
    if schema != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema: {schema!r}")

    edits = tuple(
        _edit_from_record(_mapping(item, "original_edits item"))
        for item in _list(record["original_edits"], "original_edits")
    )
    reduced_indexes = tuple(
        _integer(item, "reduced_indexes item")
        for item in _list(record["reduced_indexes"], "reduced_indexes")
    )
    if any(index < 0 or index >= len(edits) for index in reduced_indexes):
        raise ValueError("reduced index is outside original_edits")
    trials = tuple(
        _trial_from_record(_mapping(item, "trials item"))
        for item in _list(record["trials"], "trials")
    )

    try:
        minimality = Minimality(_string(record["minimality"], "minimality"))
    except ValueError as error:
        raise ValueError(f"invalid minimality: {record['minimality']!r}") from error

    return ReductionResult(
        source=_string(record["source"], "source"),
        original_edits=edits,
        reduced_indexes=reduced_indexes,
        reduced_edits=tuple(edits[index] for index in reduced_indexes),
        text=_string(record["text"], "text"),
        minimality=minimality,
        trials=trials,
    )


def dumps_result(result: ReductionResult) -> str:
    return json.dumps(
        result_to_record(result),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def loads_result(line: str) -> ReductionResult:
    try:
        value: object = json.loads(line)
    except json.JSONDecodeError as error:
        raise ValueError("invalid reduction JSON") from error
    return result_from_record(_mapping(value, "result"))


def write_jsonl(path: Path, results: Iterable[ReductionResult]) -> None:
    lines = [dumps_result(result) for result in results]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_jsonl(path: Path) -> tuple[ReductionResult, ...]:
    results: list[ReductionResult] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
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
    _require_keys(record, {"start", "before", "after"}, "edit")
    return GraphemeEdit(
        start=_integer(record["start"], "edit.start"),
        before=tuple(
            _string(item, "edit.before item") for item in _list(record["before"], "edit.before")
        ),
        after=tuple(
            _string(item, "edit.after item") for item in _list(record["after"], "edit.after")
        ),
    )


def _trial_from_record(record: Mapping[str, object]) -> ReductionTrial:
    _require_keys(record, {"edit_indexes", "text", "failed"}, "trial")
    return ReductionTrial(
        edit_indexes=tuple(
            _integer(item, "trial.edit_indexes item")
            for item in _list(record["edit_indexes"], "trial.edit_indexes")
        ),
        text=_string(record["text"], "trial.text"),
        failed=_boolean(record["failed"], "trial.failed"),
    )


def _require_keys(record: Mapping[str, object], expected: set[str], name: str) -> None:
    actual = set(record)
    if actual != expected:
        raise ValueError(
            f"{name} fields do not match schema; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    return value


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value

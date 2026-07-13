import json
from pathlib import Path

import pytest

from orthodrift.reduction import ReductionResult, reduce_failure
from orthodrift.serialization import (
    SCHEMA_VERSION,
    dumps_result,
    loads_result,
    read_jsonl,
    result_from_record,
    result_to_record,
    write_jsonl,
)
from orthodrift.text import GraphemeEdit


def _result() -> ReductionResult:
    edits = (
        GraphemeEdit.from_text(0, "Ş", "S\u0327"),
        GraphemeEdit.from_text(3, "i", "I"),
    )
    return reduce_failure(
        "Şəki",
        edits,
        lambda text: text.startswith("S\u0327") and text.endswith("I"),
    )


def test_result_round_trips_without_escaping_azerbaijani() -> None:
    result = _result()

    encoded = dumps_result(result)
    decoded = loads_result(encoded)

    assert "Şəki" in encoded
    assert "\\u015e" not in encoded
    assert decoded == result
    assert json.loads(encoded)["schema"] == SCHEMA_VERSION


def test_jsonl_round_trip(tmp_path: Path) -> None:
    result = _result()
    path = tmp_path / "results.jsonl"

    write_jsonl(path, [result, result])

    assert path.read_text(encoding="utf-8").endswith("\n")
    assert read_jsonl(path) == (result, result)


def test_empty_jsonl_is_valid(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"

    write_jsonl(path, [])

    assert path.read_text(encoding="utf-8") == ""
    assert read_jsonl(path) == ()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "orthodrift.reduction.v0", "unsupported schema"),
        ("text", "tampered", "do not reconstruct"),
        ("minimality", "perfect", "invalid minimality"),
        ("reduced_indexes", [99], "outside original_edits"),
    ],
)
def test_corrupt_top_level_records_are_rejected(field: str, value: object, message: str) -> None:
    record = result_to_record(_result())
    record[field] = value

    with pytest.raises(ValueError, match=message):
        result_from_record(record)


def test_passing_subset_cannot_be_claimed_as_the_reduced_failure() -> None:
    record = result_to_record(_result())
    record["reduced_indexes"] = []
    record["text"] = record["source"]

    with pytest.raises(ValueError, match="failing reduced-edit trial"):
        result_from_record(record)


def test_corrupt_trial_text_is_rejected() -> None:
    record = result_to_record(_result())
    trials = record["trials"]
    assert isinstance(trials, list)
    first_trial = trials[0]
    assert isinstance(first_trial, dict)
    first_trial["text"] = "tampered"

    with pytest.raises(ValueError, match="trial edits do not reconstruct"):
        result_from_record(record)


def test_extra_fields_and_blank_jsonl_records_are_rejected(tmp_path: Path) -> None:
    record = result_to_record(_result())
    record["surprise"] = True
    with pytest.raises(ValueError, match="unexpected"):
        result_from_record(record)

    path = tmp_path / "results.jsonl"
    path.write_text(f"{dumps_result(_result())}\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="blank JSONL record at line 2"):
        read_jsonl(path)


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid reduction JSON"):
        loads_result("{")

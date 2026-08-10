import json
from dataclasses import replace
from pathlib import Path

import pytest

from orthodrift._io import MAX_CASE_BYTES
from orthodrift.experiment import (
    CASE_SCHEMA_VERSION,
    case_from_record,
    case_to_record,
    load_case,
    run_case,
)
from orthodrift.reduction import Minimality
from orthodrift.text import GraphemeEdit, Relation

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "shaki-rank-flip.json"


def test_committed_case_reproduces_and_reduces_the_rank_flip() -> None:
    case = load_case(EXAMPLE)
    result = run_case(case)

    assert case.name == "shaki-decomposed-grapheme"
    assert case.mutations[0].relation is Relation.CANONICAL
    assert case.mutations[1].relation is Relation.ADVERSARIAL
    assert result.baseline_rank == 1
    assert result.full_mutant_rank == 2
    assert result.reduction.reduced_indexes == (0,)
    assert result.reduction.minimality is Minimality.GLOBAL
    assert result.rank_for(result.reduction.reduced_indexes) == 2


def test_case_schema_round_trips_with_typed_mutation_provenance() -> None:
    case = load_case(EXAMPLE)

    decoded = case_from_record(case_to_record(case))

    assert decoded == case
    assert decoded.mutations[0].rule_id == "unicode.normalize-span.nfd"
    assert decoded.mutations[0].parameters == (("form", "NFD"), ("scope", "edit-span"))
    assert decoded.mutations[0].rule_pack_id == "unicode-normalization"


def test_case_schema_preserves_explicit_grapheme_units() -> None:
    case = load_case(EXAMPLE)
    changed = case_from_record(case_to_record(case))

    assert changed.mutations[2].edit.before == ("2", "0", "2", "6")


def test_nfd_rule_supports_independent_decomposition_units() -> None:
    first = load_case(EXAMPLE).mutations[0]
    second = replace(
        first,
        mutation_id="decompose-a-acute",
        edit=GraphemeEdit.from_text(1, "Á", "A\u0301"),
    )

    assert first.as_step("ŞÁ").output_text == "S\u0327Á"
    assert second.as_step("ŞÁ").output_text == "ŞA\u0301"


def test_nfd_rule_rejects_a_padded_nonminimal_edit() -> None:
    case = load_case(EXAMPLE)
    padded = replace(
        case.mutations[0],
        edit=GraphemeEdit.from_text(0, case.query, "S\u0327əki atlası 2026"),
    )

    with pytest.raises(ValueError, match="not a minimal edit span"):
        padded.as_step(case.query)


def test_mutation_parameters_have_a_canonical_order() -> None:
    mutation = replace(
        load_case(EXAMPLE).mutations[0],
        parameters=(("z", "last"), ("a", "first")),
    )

    assert mutation.parameters == (("a", "first"), ("z", "last"))


def test_case_schema_and_target_are_validated() -> None:
    record = case_to_record(load_case(EXAMPLE))
    record["schema"] = "orthodrift.case.v0"
    with pytest.raises(ValueError, match="unsupported case schema"):
        case_from_record(record)

    record = case_to_record(load_case(EXAMPLE))
    record["target_document_id"] = "missing"
    with pytest.raises(ValueError, match="not present"):
        case_from_record(record)


def test_false_canonical_claim_is_rejected() -> None:
    record = case_to_record(load_case(EXAMPLE))
    mutations = record["mutations"]
    assert isinstance(mutations, list)
    first = mutations[0]
    assert isinstance(first, dict)
    edit = first["edit"]
    assert isinstance(edit, dict)
    edit["after"] = ["X"]

    with pytest.raises(ValueError, match="not canonically equivalent"):
        case_from_record(record)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rule_id", "unicode.normalize-span.nfc", "unsupported mutation rule"),
        ("unicode_version", "999.0", "unsupported Unicode version"),
    ],
)
def test_unregistered_provenance_is_rejected(field: str, value: object, message: str) -> None:
    record = case_to_record(load_case(EXAMPLE))
    mutations = record["mutations"]
    assert isinstance(mutations, list)
    first = mutations[0]
    assert isinstance(first, dict)
    first[field] = value

    with pytest.raises(ValueError, match=message):
        case_from_record(record)


def test_rule_parameters_and_pack_must_match_the_registered_rule() -> None:
    record = case_to_record(load_case(EXAMPLE))
    mutations = record["mutations"]
    assert isinstance(mutations, list)
    first = mutations[0]
    assert isinstance(first, dict)
    first["parameters"] = {"form": "NFC"}
    with pytest.raises(ValueError, match="parameters do not match"):
        case_from_record(record)

    record = case_to_record(load_case(EXAMPLE))
    mutations = record["mutations"]
    assert isinstance(mutations, list)
    first = mutations[0]
    assert isinstance(first, dict)
    pack = first["rule_pack"]
    assert isinstance(pack, dict)
    pack["version"] = "999"
    with pytest.raises(ValueError, match="rule pack does not match"):
        case_from_record(record)


def test_programmatic_case_rejects_boolean_limits_and_log_injection() -> None:
    case = load_case(EXAMPLE)
    with pytest.raises(ValueError, match="max_rank"):
        replace(case, max_rank=True)
    with pytest.raises(ValueError, match="proof_budget"):
        replace(case, proof_budget=True)
    with pytest.raises(ValueError, match="single-line printable"):
        replace(case, name="safe\nforged: yes")


def test_duplicate_json_fields_and_surrogates_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        f'{{"schema":"{CASE_SCHEMA_VERSION}","schema":"{CASE_SCHEMA_VERSION}"}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate JSON field"):
        load_case(duplicate)

    record = case_to_record(load_case(EXAMPLE))
    record["query"] = "\ud800"
    surrogate = tmp_path / "surrogate.json"
    surrogate.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="Unicode scalar values"):
        load_case(surrogate)


def test_case_loader_and_work_budget_are_bounded(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_CASE_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        load_case(oversized)

    case = load_case(EXAMPLE)
    with pytest.raises(ValueError, match="cannot exceed 64 mutations"):
        replace(case, mutations=case.mutations * 65)
    with pytest.raises(ValueError, match="proof_budget"):
        replace(case, proof_budget=100_001)

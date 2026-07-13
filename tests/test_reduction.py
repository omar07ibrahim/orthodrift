import pytest

from orthodrift.reduction import Minimality, reduce_failure
from orthodrift.retrieval import BM25Index, Document
from orthodrift.text import GraphemeEdit, apply_grapheme_edits, graphemes


def test_reducer_finds_the_edit_that_flips_a_retrieval_rank() -> None:
    index = BM25Index(
        [
            Document("distractor", "atlası tarixi"),
            Document("target", "Şəki atlası sənətkarlıq"),
        ]
    )
    source = "Şəki atlası 2026"
    source_clusters = graphemes(source)
    edits = (
        GraphemeEdit.from_text(start=0, before="Ş", after="S\u0327"),
        GraphemeEdit.from_text(start=3, before="i", after="I"),
        GraphemeEdit.from_text(start=source_clusters.index("2"), before="2026", after="2027"),
    )

    def target_lost_rank_one(query: str) -> bool:
        return index.rank_of(query, "target") != 1

    assert target_lost_rank_one(source) is False
    assert target_lost_rank_one(apply_grapheme_edits(source, edits)) is True

    result = reduce_failure(source, edits, target_lost_rank_one)

    assert result.reduced_indexes == (0,)
    assert result.reduced_edits == (edits[0],)
    assert result.text.startswith("S\u0327əki")
    assert result.minimality is Minimality.GLOBAL
    assert result.evaluations == len({trial.edit_indexes for trial in result.trials})


def test_reducer_proves_a_two_edit_interaction() -> None:
    edits = (
        GraphemeEdit.from_text(0, "a", "X"),
        GraphemeEdit.from_text(1, "b", "Y"),
        GraphemeEdit.from_text(2, "c", "Z"),
    )

    result = reduce_failure(
        "abc",
        edits,
        lambda text: "X" in text and "Y" in text,
    )

    assert result.reduced_indexes == (0, 1)
    assert result.text == "XYc"
    assert result.minimality is Minimality.GLOBAL
    assert all(not trial.failed for trial in result.trials if len(trial.edit_indexes) == 1)


def test_zero_proof_budget_returns_an_honest_one_minimal_result() -> None:
    edits = (
        GraphemeEdit.from_text(0, "a", "X"),
        GraphemeEdit.from_text(1, "b", "Y"),
        GraphemeEdit.from_text(2, "c", "Z"),
    )

    result = reduce_failure(
        "abc",
        edits,
        lambda text: sum(character in text for character in "XYZ") >= 2,
        proof_budget=0,
    )

    assert len(result.reduced_edits) == 2
    assert result.minimality is Minimality.ONE_MINIMAL


def test_proof_budget_can_be_exhausted_without_overclaiming() -> None:
    edits = tuple(
        GraphemeEdit.from_text(index, character, character.upper())
        for index, character in enumerate("abcdef")
    )

    result = reduce_failure(
        "abcdef",
        edits,
        lambda text: sum(character.isupper() for character in text) >= 3,
        proof_budget=1,
    )

    assert len(result.reduced_edits) == 3
    assert result.minimality is Minimality.ONE_MINIMAL


def test_global_proof_escapes_a_non_monotone_local_minimum() -> None:
    source = "abcdef"
    edits = tuple(
        GraphemeEdit.from_text(index, character, character.upper())
        for index, character in enumerate(source)
    )

    def fails(text: str) -> bool:
        active = {index for index, character in enumerate(text) if character.isupper()}
        return active == {0, 1, 2} or 5 in active

    local = reduce_failure(source, edits, fails, proof_budget=0)
    proved = reduce_failure(source, edits, fails, proof_budget=100)

    assert local.reduced_indexes == (0, 1, 2)
    assert local.minimality is Minimality.ONE_MINIMAL
    assert proved.reduced_indexes == (5,)
    assert proved.minimality is Minimality.GLOBAL


def test_reducer_requires_a_passing_baseline_and_failing_mutant() -> None:
    edit = GraphemeEdit.from_text(0, "a", "A")

    with pytest.raises(ValueError, match="already fails"):
        reduce_failure("a", (edit,), lambda _: True)

    with pytest.raises(ValueError, match="does not fail"):
        reduce_failure("a", (edit,), lambda _: False)


def test_invalid_proof_budget_is_rejected() -> None:
    with pytest.raises(ValueError, match="proof_budget"):
        reduce_failure("a", (), lambda _: False, proof_budget=-1)

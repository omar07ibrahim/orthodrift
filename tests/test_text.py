from dataclasses import FrozenInstanceError

import pytest

from orthodrift.text import (
    GraphemeEdit,
    Relation,
    TextVariant,
    TransformStep,
    apply_grapheme_edits,
    diff_graphemes,
    graphemes,
)


def test_graphemes_keep_combining_marks_and_emoji_together() -> None:
    assert graphemes("A\u0301") == ("A\u0301",)
    assert graphemes("👩🏽‍💻") == ("👩🏽‍💻",)
    assert graphemes("") == ()


def test_edit_coordinates_count_graphemes_not_code_points() -> None:
    source = "A\u0301zərbaycan"
    edit = GraphemeEdit.from_text(start=0, before="A\u0301", after="A")

    assert edit.end == 1
    assert apply_grapheme_edits(source, (edit,)) == "Azərbaycan"


def test_multiple_edits_are_applied_against_the_same_input() -> None:
    edits = (
        GraphemeEdit.from_text(start=0, before="a", after="A"),
        GraphemeEdit.from_text(start=3, before="d", after="D"),
    )

    assert apply_grapheme_edits("abcd", edits) == "AbcD"


def test_insertions_can_share_a_source_boundary() -> None:
    edits = (
        GraphemeEdit.from_text(start=1, before="", after="X"),
        GraphemeEdit.from_text(start=1, before="", after="Y"),
        GraphemeEdit.from_text(start=1, before="b", after="B"),
    )

    assert apply_grapheme_edits("abc", edits) == "aXYBc"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("kitab", "Kitab!"),
        ("a\u0301bc", "á"),
        ("salam", ""),
        ("", "salam"),
        ("abab", "aXab"),
    ],
)
def test_grapheme_diff_reconstructs_target(before: str, after: str) -> None:
    edits = diff_graphemes(before, after)

    assert apply_grapheme_edits(before, edits) == after


def test_grapheme_diff_of_equal_text_is_empty() -> None:
    assert diff_graphemes("eyni", "eyni") == ()


def test_grapheme_diff_uses_a_minimum_edit_alignment() -> None:
    edits = diff_graphemes("tide", "diet")
    operation_count = sum(max(len(edit.before), len(edit.after)) for edit in edits)

    assert operation_count == 3
    assert apply_grapheme_edits("tide", edits) == "diet"


@pytest.mark.parametrize(
    ("text", "edits", "message"),
    [
        (
            "abc",
            (GraphemeEdit.from_text(0, "b", "x"),),
            "expected",
        ),
        (
            "abc",
            (
                GraphemeEdit.from_text(1, "bc", "x"),
                GraphemeEdit.from_text(2, "c", "y"),
            ),
            "overlap",
        ),
        (
            "abc",
            (GraphemeEdit.from_text(4, "", "x"),),
            "past the input",
        ),
    ],
)
def test_invalid_edits_fail_loudly(
    text: str, edits: tuple[GraphemeEdit, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        apply_grapheme_edits(text, edits)


def test_transform_step_reconstructs_its_output() -> None:
    edit = GraphemeEdit.from_text(start=1, before="e\u0301", after="é")
    step = TransformStep.from_edits(
        rule_id="unicode.nfc",
        relation=Relation.CANONICAL,
        input_text="te\u0301st",
        edits=(edit,),
        parameters=(("form", "NFC"),),
    )

    assert step.output_text == "tést"

    with pytest.raises(ValueError, match="do not reconstruct"):
        TransformStep(
            rule_id=step.rule_id,
            relation=step.relation,
            input_text=step.input_text,
            output_text="tampered",
            edits=step.edits,
        )


def test_variant_rejects_broken_history() -> None:
    variant = TextVariant.original("te\u0301st")
    step = TransformStep.from_edits(
        rule_id="unicode.nfc",
        relation=Relation.CANONICAL,
        input_text=variant.text,
        edits=(GraphemeEdit.from_text(1, "e\u0301", "é"),),
    )

    changed = variant.apply(step)

    assert changed.source == "te\u0301st"
    assert changed.text == "tést"
    assert changed.steps == (step,)

    with pytest.raises(ValueError, match="current variant"):
        TextVariant.original("other").apply(step)


def test_provenance_objects_are_immutable() -> None:
    variant = TextVariant.original("salam")

    with pytest.raises(FrozenInstanceError):
        variant.text = "changed"  # type: ignore[misc]

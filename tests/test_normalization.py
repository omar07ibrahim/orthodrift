import unicodedata

import pytest

from orthodrift.normalization import (
    NormalizationForm,
    normalization_step,
    normalize_variant,
)
from orthodrift.text import Relation, TextVariant, apply_grapheme_edits


@pytest.mark.parametrize(
    ("form", "source", "expected"),
    [
        (NormalizationForm.NFC, "te\u0301st", "tést"),
        (NormalizationForm.NFD, "tést", "te\u0301st"),
        (NormalizationForm.NFD, "a\u0315\u0300", "a\u0300\u0315"),
    ],
)
def test_canonical_forms_create_reproducible_steps(
    form: NormalizationForm, source: str, expected: str
) -> None:
    step = normalization_step(source, form)

    assert step is not None
    assert step.output_text == expected
    assert step.relation is Relation.CANONICAL
    assert apply_grapheme_edits(source, step.edits) == expected
    assert ("form", form.value) in step.parameters
    assert ("unicode_version", unicodedata.unidata_version) in step.parameters


@pytest.mark.parametrize(
    ("form", "source", "expected"),
    [
        (NormalizationForm.NFKC, "①", "1"),
        (NormalizationForm.NFKD, "ﬀ", "ff"),
    ],
)
def test_compatibility_forms_do_not_claim_equivalence(
    form: NormalizationForm, source: str, expected: str
) -> None:
    step = normalization_step(source, form)

    assert step is not None
    assert step.output_text == expected
    assert step.relation is Relation.UNKNOWN


def test_normalization_does_not_record_no_op_steps() -> None:
    variant = TextVariant.original("Azərbaycan")

    assert normalization_step(variant.text, NormalizationForm.NFC) is None
    assert normalize_variant(variant, NormalizationForm.NFC) is variant


def test_normalized_variant_keeps_source_and_history() -> None:
    variant = TextVariant.original("te\u0301st")

    normalized = normalize_variant(variant, NormalizationForm.NFC)

    assert normalized.source == variant.source
    assert normalized.text == "tést"
    assert len(normalized.steps) == 1
    assert normalized.steps[0].rule_id == "unicode.normalize.nfc"

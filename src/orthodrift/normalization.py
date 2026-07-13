"""Typed Unicode normalization transformations."""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from orthodrift.text import Relation, TextVariant, TransformStep, diff_graphemes


class NormalizationForm(StrEnum):
    NFC = "NFC"
    NFD = "NFD"
    NFKC = "NFKC"
    NFKD = "NFKD"

    @property
    def relation(self) -> Relation:
        if self in {NormalizationForm.NFC, NormalizationForm.NFD}:
            return Relation.CANONICAL
        return Relation.UNKNOWN


def normalization_step(text: str, form: NormalizationForm) -> TransformStep | None:
    """Build a normalization step, or return ``None`` when text is unchanged."""

    normalized = unicodedata.normalize(form.value, text)
    if normalized == text:
        return None

    return TransformStep.from_edits(
        rule_id=f"unicode.normalize.{form.lower()}",
        relation=form.relation,
        input_text=text,
        edits=diff_graphemes(text, normalized),
        parameters=(
            ("form", form.value),
            ("unicode_version", unicodedata.unidata_version),
        ),
    )


def normalize_variant(variant: TextVariant, form: NormalizationForm) -> TextVariant:
    """Normalize the current text without adding a no-op provenance step."""

    step = normalization_step(variant.text, form)
    return variant if step is None else variant.apply(step)

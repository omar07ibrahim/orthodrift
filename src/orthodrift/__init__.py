"""Tools for measuring orthographic failures in multilingual retrieval."""

from orthodrift.normalization import NormalizationForm, normalization_step, normalize_variant
from orthodrift.text import (
    GraphemeEdit,
    Relation,
    TextVariant,
    TransformStep,
    apply_grapheme_edits,
    diff_graphemes,
    graphemes,
)

__all__ = [
    "GraphemeEdit",
    "NormalizationForm",
    "Relation",
    "TextVariant",
    "TransformStep",
    "apply_grapheme_edits",
    "diff_graphemes",
    "graphemes",
    "normalization_step",
    "normalize_variant",
]

__version__ = "0.0.0"

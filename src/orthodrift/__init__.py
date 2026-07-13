"""Tools for measuring orthographic failures in multilingual retrieval."""

from orthodrift.normalization import NormalizationForm, normalization_step, normalize_variant
from orthodrift.retrieval import BM25Index, Document, SearchHit, tokenize_words
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
    "BM25Index",
    "Document",
    "GraphemeEdit",
    "NormalizationForm",
    "Relation",
    "SearchHit",
    "TextVariant",
    "TransformStep",
    "apply_grapheme_edits",
    "diff_graphemes",
    "graphemes",
    "normalization_step",
    "normalize_variant",
    "tokenize_words",
]

__version__ = "0.0.0"

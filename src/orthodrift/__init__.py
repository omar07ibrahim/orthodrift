"""Tools for measuring orthographic failures in multilingual retrieval."""

from orthodrift.text import (
    GraphemeEdit,
    Relation,
    TextVariant,
    TransformStep,
    apply_grapheme_edits,
    graphemes,
)

__all__ = [
    "GraphemeEdit",
    "Relation",
    "TextVariant",
    "TransformStep",
    "apply_grapheme_edits",
    "graphemes",
]

__version__ = "0.0.0"

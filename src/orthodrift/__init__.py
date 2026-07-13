"""Tools for measuring orthographic failures in multilingual retrieval."""

from orthodrift.normalization import NormalizationForm, normalization_step, normalize_variant
from orthodrift.reduction import (
    Minimality,
    ReductionResult,
    ReductionTrial,
    reduce_failure,
)
from orthodrift.retrieval import BM25Index, Document, SearchHit, tokenize_words
from orthodrift.serialization import (
    SCHEMA_VERSION,
    dumps_result,
    loads_result,
    read_jsonl,
    result_from_record,
    result_to_record,
    write_jsonl,
)
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
    "Minimality",
    "NormalizationForm",
    "ReductionResult",
    "ReductionTrial",
    "SCHEMA_VERSION",
    "Relation",
    "SearchHit",
    "TextVariant",
    "TransformStep",
    "apply_grapheme_edits",
    "diff_graphemes",
    "dumps_result",
    "graphemes",
    "loads_result",
    "normalization_step",
    "normalize_variant",
    "reduce_failure",
    "read_jsonl",
    "result_from_record",
    "result_to_record",
    "tokenize_words",
    "write_jsonl",
]

__version__ = "0.0.0"

"""Deterministic lexical retrieval baselines."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from math import log

import regex

from orthodrift._schema import number, string

Tokenizer = Callable[[str], tuple[str, ...]]

RETRIEVER_ID = "orthodrift.bm25.v1"
TOKENIZER_ID = "orthodrift.unicode-words.v1"
TIE_BREAK_ID = "document-order"
DEFAULT_K1 = 1.2
DEFAULT_B = 0.75
TOKENIZER_PATTERN = r"[\p{L}\p{N}](?:[\p{L}\p{M}\p{N}]|['’](?=[\p{L}\p{N}]))*"

_WORD = regex.compile(TOKENIZER_PATTERN)


def tokenize_words(text: str, *, casefold: bool = True) -> tuple[str, ...]:
    """Tokenize words without applying implicit Unicode normalization."""

    tokens = tuple(_WORD.findall(text))
    return tuple(token.casefold() for token in tokens) if casefold else tokens


@dataclass(frozen=True, slots=True)
class Document:
    document_id: str
    text: str

    def __post_init__(self) -> None:
        string(self.document_id, "document_id")
        string(self.text, "document text")
        if not self.document_id or self.document_id.strip() != self.document_id:
            raise ValueError("document_id must be a non-empty, trimmed string")


@dataclass(frozen=True, slots=True)
class SearchHit:
    document_id: str
    score: float
    rank: int


class BM25Index:
    """A small BM25 index with explicit tokenization and stable tie-breaking."""

    def __init__(
        self,
        documents: Iterable[Document],
        *,
        tokenizer: Tokenizer = tokenize_words,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        validated_k1 = number(k1, "k1")
        validated_b = number(b, "b")
        if validated_k1 <= 0:
            raise ValueError("k1 must be greater than zero")
        if not 0 <= validated_b <= 1:
            raise ValueError("b must be between zero and one")

        self.documents = tuple(documents)
        self.tokenizer = tokenizer
        self.k1 = validated_k1
        self.b = validated_b

        identifiers = [document.document_id for document in self.documents]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("document identifiers must be unique")

        term_frequencies = [Counter(tokenizer(document.text)) for document in self.documents]
        self._document_lengths = tuple(sum(counts.values()) for counts in term_frequencies)
        self.average_document_length = (
            sum(self._document_lengths) / len(self._document_lengths)
            if self._document_lengths
            else 0.0
        )

        postings: defaultdict[str, list[tuple[int, int]]] = defaultdict(list)
        for document_index, counts in enumerate(term_frequencies):
            for term, frequency in counts.items():
                postings[term].append((document_index, frequency))
        self._postings = {term: tuple(entries) for term, entries in postings.items()}

    def search(self, query: str, *, limit: int = 10) -> tuple[SearchHit, ...]:
        string(query, "query")
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit must be greater than zero")
        if not self.documents:
            return ()

        query_terms = tuple(dict.fromkeys(self.tokenizer(query)))
        if not query_terms:
            return ()

        scores = [0.0] * len(self.documents)
        document_count = len(self.documents)

        for term in query_terms:
            entries = self._postings.get(term)
            if not entries:
                continue
            document_frequency = len(entries)
            inverse_document_frequency = log(
                1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
            )

            for document_index, term_frequency in entries:
                length_ratio = self._document_lengths[document_index] / self.average_document_length
                denominator = term_frequency + self.k1 * (1 - self.b + self.b * length_ratio)
                scores[document_index] += inverse_document_frequency * (
                    term_frequency * (self.k1 + 1) / denominator
                )

        ranked = sorted(
            ((document_index, score) for document_index, score in enumerate(scores) if score > 0),
            key=lambda item: (-item[1], item[0]),
        )[:limit]

        return tuple(
            SearchHit(
                document_id=self.documents[document_index].document_id,
                score=score,
                rank=rank,
            )
            for rank, (document_index, score) in enumerate(ranked, start=1)
        )

    def rank_of(self, query: str, document_id: str) -> int | None:
        for hit in self.search(query, limit=len(self.documents) or 1):
            if hit.document_id == document_id:
                return hit.rank
        return None


@dataclass(frozen=True, slots=True)
class BM25Spec:
    implementation: str = RETRIEVER_ID
    k1: float = DEFAULT_K1
    b: float = DEFAULT_B
    tie_break: str = TIE_BREAK_ID
    tokenizer: str = TOKENIZER_ID
    tokenizer_pattern: str = TOKENIZER_PATTERN
    casefold: bool = True

    def __post_init__(self) -> None:
        validated_k1 = number(self.k1, "k1")
        validated_b = number(self.b, "b")
        object.__setattr__(self, "k1", validated_k1)
        object.__setattr__(self, "b", validated_b)
        if self.implementation != RETRIEVER_ID:
            raise ValueError(f"unsupported retriever: {self.implementation!r}")
        if validated_k1 <= 0:
            raise ValueError("k1 must be greater than zero")
        if not 0 <= validated_b <= 1:
            raise ValueError("b must be between zero and one")
        if self.tie_break != TIE_BREAK_ID:
            raise ValueError(f"unsupported tie break: {self.tie_break!r}")
        if self.tokenizer != TOKENIZER_ID:
            raise ValueError(f"unsupported tokenizer: {self.tokenizer!r}")
        if self.tokenizer_pattern != TOKENIZER_PATTERN:
            raise ValueError("unsupported tokenizer pattern")
        if type(self.casefold) is not bool:
            raise ValueError("casefold must be boolean")

    def build(self, documents: Iterable[Document]) -> BM25Index:
        return BM25Index(
            documents,
            tokenizer=partial(tokenize_words, casefold=self.casefold),
            k1=self.k1,
            b=self.b,
        )


DEFAULT_BM25_SPEC = BM25Spec()

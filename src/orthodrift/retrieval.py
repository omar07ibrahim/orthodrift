"""Deterministic lexical retrieval baselines."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import log

import regex

Tokenizer = Callable[[str], tuple[str, ...]]

_WORD = regex.compile(r"[\p{L}\p{N}](?:[\p{L}\p{M}\p{N}]|['’](?=[\p{L}\p{N}]))*")


def tokenize_words(text: str, *, casefold: bool = True) -> tuple[str, ...]:
    """Tokenize words without applying implicit Unicode normalization."""

    tokens = tuple(_WORD.findall(text))
    return tuple(token.casefold() for token in tokens) if casefold else tokens


@dataclass(frozen=True, slots=True)
class Document:
    document_id: str
    text: str

    def __post_init__(self) -> None:
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
        k1: float = 1.2,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than zero")
        if not 0 <= b <= 1:
            raise ValueError("b must be between zero and one")

        self.documents = tuple(documents)
        self.tokenizer = tokenizer
        self.k1 = k1
        self.b = b

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
        if limit <= 0:
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

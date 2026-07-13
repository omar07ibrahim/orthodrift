import pytest

from orthodrift.retrieval import BM25Index, Document, tokenize_words


def test_tokenizer_casefolds_without_normalizing() -> None:
    assert tokenize_words("GƏNCƏ 2026") == ("gəncə", "2026")
    assert tokenize_words("te\u0301st") == ("te\u0301st",)
    assert tokenize_words("GƏNCƏ", casefold=False) == ("GƏNCƏ",)


def test_bm25_ranks_the_matching_document_first() -> None:
    index = BM25Index(
        [
            Document("baku", "Bakı Azərbaycanın paytaxtıdır"),
            Document("ganja", "Gəncə Azərbaycanın böyük şəhərlərindən biridir"),
            Document("language", "Azərbaycan dili türk dillərindəndir"),
        ]
    )

    hits = index.search("Bakı paytaxtıdır")

    assert [hit.document_id for hit in hits] == ["baku"]
    assert hits[0].rank == 1
    assert hits[0].score > 0
    assert index.rank_of("Bakı paytaxtıdır", "baku") == 1


def test_rare_terms_outweigh_common_terms() -> None:
    index = BM25Index(
        [
            Document("rare", "ortaq nadir"),
            Document("common-1", "ortaq"),
            Document("common-2", "ortaq"),
        ],
        b=0,
    )

    hits = index.search("ortaq nadir")

    assert hits[0].document_id == "rare"
    assert hits[0].score > hits[1].score


def test_ties_preserve_document_order() -> None:
    index = BM25Index(
        [
            Document("second-alphabetically", "salam"),
            Document("first-alphabetically", "salam"),
        ]
    )

    assert [hit.document_id for hit in index.search("salam")] == [
        "second-alphabetically",
        "first-alphabetically",
    ]


def test_repeated_query_terms_do_not_change_scores() -> None:
    index = BM25Index([Document("greeting", "salam dünya")])

    once = index.search("salam")
    repeated = index.search("salam salam salam")

    assert repeated == once


def test_precomposed_and_decomposed_queries_can_diverge() -> None:
    index = BM25Index([Document("shaki", "Şəki")])

    assert index.rank_of("Şəki", "shaki") == 1
    assert index.rank_of("S\u0327əki", "shaki") is None


def test_empty_index_and_unknown_terms_have_no_hits() -> None:
    assert BM25Index([]).search("salam") == ()
    index = BM25Index([Document("known", "salam")])
    assert index.search("naməlum") == ()
    assert index.search("... !!!") == ()


def test_duplicate_document_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        BM25Index([Document("same", "a"), Document("same", "b")])


@pytest.mark.parametrize("k1", [0, -1])
def test_invalid_k1_is_rejected(k1: float) -> None:
    with pytest.raises(ValueError, match="k1"):
        BM25Index([], k1=k1)


@pytest.mark.parametrize("b", [-0.1, 1.1])
def test_invalid_b_is_rejected(b: float) -> None:
    with pytest.raises(ValueError, match="between"):
        BM25Index([], b=b)


def test_invalid_document_id_and_limit_are_rejected() -> None:
    with pytest.raises(ValueError, match="document_id"):
        Document(" ", "text")

    with pytest.raises(ValueError, match="limit"):
        BM25Index([Document("one", "text")]).search("text", limit=0)

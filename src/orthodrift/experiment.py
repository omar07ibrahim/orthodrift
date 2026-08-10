"""Reproducible retrieval failure cases."""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from orthodrift._io import MAX_CASE_BYTES, read_text_limited
from orthodrift._schema import (
    array,
    integer,
    loads_mapping,
    mapping,
    nullable_integer,
    nullable_string,
    require_keys,
    string,
)
from orthodrift.reduction import ReductionResult, reduce_failure
from orthodrift.retrieval import DEFAULT_BM25_SPEC, BM25Spec, Document
from orthodrift.rules import validate_rule_claim
from orthodrift.text import GraphemeEdit, Relation, TransformStep, apply_grapheme_edits

CASE_SCHEMA_VERSION = "orthodrift.case.v1"
MAX_DOCUMENTS = 4_096
MAX_MUTATIONS = 64
MAX_PROOF_BUDGET = 100_000
_RESERVED_PARAMETERS = {"rule_pack_id", "rule_pack_version", "unicode_version"}
_ENGINE_PATHS = (
    "__init__.py",
    "_io.py",
    "_schema.py",
    "cli.py",
    "experiment.py",
    "normalization.py",
    "reduction.py",
    "report.py",
    "retrieval.py",
    "rules.py",
    "run_serialization.py",
    "serialization.py",
    "text.py",
)


@dataclass(frozen=True, slots=True)
class CaseMutation:
    mutation_id: str
    rule_id: str
    relation: Relation
    edit: GraphemeEdit
    rule_pack_id: str
    rule_pack_version: str
    unicode_version: str | None
    parameters: tuple[tuple[str, str], ...] = ()
    seed: int | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.mutation_id, "mutation_id"),
            (self.rule_id, "rule_id"),
            (self.rule_pack_id, "rule_pack_id"),
        ):
            string(value, name)
            if not value or value.strip() != value:
                raise ValueError(f"{name} must be a non-empty, trimmed string")
            if any(character.isspace() for character in value):
                raise ValueError(f"{name} cannot contain whitespace")
        if not isinstance(self.relation, Relation):
            raise ValueError("relation must be a Relation value")
        string(self.rule_pack_version, "rule_pack_version")
        if not self.rule_pack_version or self.rule_pack_version.strip() != self.rule_pack_version:
            raise ValueError("rule_pack_version must be a non-empty, trimmed string")
        if self.unicode_version is not None:
            string(self.unicode_version, "unicode_version")
            if not self.unicode_version or self.unicode_version.strip() != self.unicode_version:
                raise ValueError("unicode_version must be a non-empty, trimmed string or null")
        if self.seed is not None and type(self.seed) is not int:
            raise ValueError("seed must be an integer or null")

        if any(type(key) is not str or type(value) is not str for key, value in self.parameters):
            raise ValueError("parameter names and values must be strings")
        keys = [key for key, _ in self.parameters]
        for key, value in self.parameters:
            string(key, "parameter name")
            string(value, f"parameter {key!r}")
        if any(not key or key.strip() != key for key in keys):
            raise ValueError("parameter names must be non-empty and trimmed")
        if len(keys) != len(set(keys)):
            raise ValueError("parameter names must be unique")
        if _RESERVED_PARAMETERS.intersection(keys):
            raise ValueError("rule-pack and Unicode fields are reserved parameters")
        object.__setattr__(self, "parameters", tuple(sorted(self.parameters)))

    def as_step(self, input_text: str) -> TransformStep:
        metadata: tuple[tuple[str, str], ...] = (
            ("rule_pack_id", self.rule_pack_id),
            ("rule_pack_version", self.rule_pack_version),
        )
        if self.unicode_version is not None:
            metadata = (*metadata, ("unicode_version", self.unicode_version))
        step = TransformStep.from_edits(
            rule_id=self.rule_id,
            relation=self.relation,
            input_text=input_text,
            edits=(self.edit,),
            parameters=(
                *self.parameters,
                *metadata,
            ),
            seed=self.seed,
        )
        if self.relation is Relation.CANONICAL and unicodedata.normalize(
            "NFD", input_text
        ) != unicodedata.normalize("NFD", step.output_text):
            raise ValueError("canonical mutation is not canonically equivalent")
        validate_rule_claim(
            rule_id=self.rule_id,
            relation=self.relation,
            edit=self.edit,
            parameters=self.parameters,
            rule_pack_id=self.rule_pack_id,
            rule_pack_version=self.rule_pack_version,
            unicode_version=self.unicode_version,
            input_text=input_text,
            output_text=step.output_text,
        )
        return step


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    name: str
    documents: tuple[Document, ...]
    query: str
    target_document_id: str
    max_rank: int
    mutations: tuple[CaseMutation, ...]
    proof_budget: int = 4_096

    def __post_init__(self) -> None:
        string(self.name, "case name")
        if not self.name or self.name.strip() != self.name:
            raise ValueError("case name must be a non-empty, trimmed string")
        if not self.name.isprintable() or "\n" in self.name or "\r" in self.name:
            raise ValueError("case name must be single-line printable text")
        string(self.query, "case query")
        string(self.target_document_id, "target_document_id")
        if not self.documents:
            raise ValueError("case must contain at least one document")
        if len(self.documents) > MAX_DOCUMENTS:
            raise ValueError(f"case cannot exceed {MAX_DOCUMENTS} documents")
        for document in self.documents:
            string(document.document_id, "document_id")
            string(document.text, f"document {document.document_id!r} text")
        identifiers = [document.document_id for document in self.documents]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("case document identifiers must be unique")
        if self.target_document_id not in identifiers:
            raise ValueError("target_document_id is not present in documents")
        if type(self.max_rank) is not int or self.max_rank <= 0:
            raise ValueError("max_rank must be greater than zero")
        if not self.mutations:
            raise ValueError("case must contain at least one mutation")
        if len(self.mutations) > MAX_MUTATIONS:
            raise ValueError(f"case cannot exceed {MAX_MUTATIONS} mutations")
        mutation_ids = [mutation.mutation_id for mutation in self.mutations]
        if len(mutation_ids) != len(set(mutation_ids)):
            raise ValueError("case mutation identifiers must be unique")
        if type(self.proof_budget) is not int or not 0 <= self.proof_budget <= MAX_PROOF_BUDGET:
            raise ValueError(f"proof_budget must be between 0 and {MAX_PROOF_BUDGET}")
        text_bytes = len(self.query.encode("utf-8")) + sum(
            len(document.text.encode("utf-8")) for document in self.documents
        )
        if text_bytes > MAX_CASE_BYTES:
            raise ValueError(f"case query and documents cannot exceed {MAX_CASE_BYTES} UTF-8 bytes")

        apply_grapheme_edits(self.query, self.edits)
        for mutation in self.mutations:
            mutation.as_step(self.query)

    @property
    def edits(self) -> tuple[GraphemeEdit, ...]:
        return tuple(mutation.edit for mutation in self.mutations)


@dataclass(frozen=True, slots=True)
class RuntimeFingerprint:
    orthodrift_version: str
    engine_sha256: str
    python_implementation: str
    python_version: str
    python_unicode_version: str
    regex_version: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.orthodrift_version, "orthodrift_version"),
            (self.python_implementation, "python_implementation"),
            (self.python_version, "python_version"),
            (self.python_unicode_version, "python_unicode_version"),
            (self.regex_version, "regex_version"),
        ):
            if not value or value.strip() != value:
                raise ValueError(f"{name} must be a non-empty, trimmed string")
        if len(self.engine_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.engine_sha256
        ):
            raise ValueError("engine_sha256 must be a lowercase SHA-256 digest")

    @classmethod
    def capture(cls) -> RuntimeFingerprint:
        return cls(
            orthodrift_version=importlib.metadata.version("orthodrift"),
            engine_sha256=_engine_digest(),
            python_implementation=platform.python_implementation().lower(),
            python_version=platform.python_version(),
            python_unicode_version=unicodedata.unidata_version,
            regex_version=importlib.metadata.version("regex"),
        )


@dataclass(frozen=True, slots=True)
class RankMeasurement:
    edit_indexes: tuple[int, ...]
    target_rank: int | None

    def __post_init__(self) -> None:
        if self.edit_indexes != tuple(sorted(set(self.edit_indexes))):
            raise ValueError("measurement indexes must be sorted and unique")
        if any(type(index) is not int or index < 0 for index in self.edit_indexes):
            raise ValueError("measurement indexes must be non-negative integers")
        _validate_rank(self.target_rank, "target_rank")


@dataclass(frozen=True, slots=True)
class RetrievalCaseRun:
    case: RetrievalCase
    retriever: BM25Spec
    runtime: RuntimeFingerprint
    measurements: tuple[RankMeasurement, ...]
    reduction: ReductionResult

    def __post_init__(self) -> None:
        if self.reduction.source != self.case.query:
            raise ValueError("reduction source does not match the case query")
        if self.reduction.original_edits != self.case.edits:
            raise ValueError("reduction edits do not match the case mutations")
        measurement_indexes = tuple(item.edit_indexes for item in self.measurements)
        trial_indexes = tuple(trial.edit_indexes for trial in self.reduction.trials)
        if measurement_indexes != trial_indexes:
            raise ValueError("rank measurements do not match the reduction trials")

        for measurement, trial in zip(self.measurements, self.reduction.trials, strict=True):
            if any(index >= len(self.case.edits) for index in measurement.edit_indexes):
                raise ValueError("measurement index is outside the case mutations")
            if measurement.target_rank is not None and measurement.target_rank > len(
                self.case.documents
            ):
                raise ValueError("measured rank exceeds the case corpus size")
            if trial.failed != self.failed_at(measurement.target_rank):
                raise ValueError("stored failure flag does not match the measured rank")

        if self.failed_at(self.baseline_rank):
            raise ValueError("stored baseline rank does not pass the case threshold")
        if not self.failed_at(self.full_mutant_rank):
            raise ValueError("stored full-mutant rank does not fail the case threshold")

    @property
    def baseline_rank(self) -> int | None:
        return self.rank_for(())

    @property
    def full_mutant_rank(self) -> int | None:
        return self.rank_for(tuple(range(len(self.case.edits))))

    def rank_for(self, edit_indexes: tuple[int, ...]) -> int | None:
        for measurement in self.measurements:
            if measurement.edit_indexes == edit_indexes:
                return measurement.target_rank
        raise ValueError(f"run has no rank measurement for edit indexes {edit_indexes!r}")

    def failed_at(self, rank: int | None) -> bool:
        return rank is None or rank > self.case.max_rank


def run_case(
    case: RetrievalCase,
    retriever: BM25Spec = DEFAULT_BM25_SPEC,
) -> RetrievalCaseRun:
    index = retriever.build(case.documents)

    def fails(query: str) -> bool:
        rank = index.rank_of(query, case.target_document_id)
        return rank is None or rank > case.max_rank

    reduction = reduce_failure(
        case.query,
        case.edits,
        fails,
        proof_budget=case.proof_budget,
    )
    measurements = tuple(
        RankMeasurement(
            edit_indexes=trial.edit_indexes,
            target_rank=index.rank_of(trial.text, case.target_document_id),
        )
        for trial in reduction.trials
    )
    return RetrievalCaseRun(
        case=case,
        retriever=retriever,
        runtime=RuntimeFingerprint.capture(),
        measurements=measurements,
        reduction=reduction,
    )


def load_case(path: Path) -> RetrievalCase:
    payload = read_text_limited(path, max_bytes=MAX_CASE_BYTES)
    return case_from_record(loads_mapping(payload, "case"))


def case_to_record(case: RetrievalCase) -> dict[str, object]:
    return {
        "schema": CASE_SCHEMA_VERSION,
        "name": case.name,
        "documents": [
            {"id": document.document_id, "text": document.text} for document in case.documents
        ],
        "query": case.query,
        "target_document_id": case.target_document_id,
        "max_rank": case.max_rank,
        "mutations": [_mutation_to_record(mutation) for mutation in case.mutations],
        "proof_budget": case.proof_budget,
    }


def case_from_record(record: Mapping[str, object]) -> RetrievalCase:
    require_keys(
        record,
        {
            "schema",
            "name",
            "documents",
            "query",
            "target_document_id",
            "max_rank",
            "mutations",
            "proof_budget",
        },
        "case",
    )
    schema = string(record["schema"], "schema")
    if schema != CASE_SCHEMA_VERSION:
        raise ValueError(f"unsupported case schema: {schema!r}")

    return RetrievalCase(
        name=string(record["name"], "name"),
        documents=tuple(
            _document_from_record(mapping(item, "documents item"))
            for item in array(record["documents"], "documents")
        ),
        query=string(record["query"], "query"),
        target_document_id=string(record["target_document_id"], "target_document_id"),
        max_rank=integer(record["max_rank"], "max_rank"),
        mutations=tuple(
            _mutation_from_record(mapping(item, "mutations item"))
            for item in array(record["mutations"], "mutations")
        ),
        proof_budget=integer(record["proof_budget"], "proof_budget"),
    )


def _document_from_record(record: Mapping[str, object]) -> Document:
    require_keys(record, {"id", "text"}, "document")
    return Document(
        document_id=string(record["id"], "document.id"),
        text=string(record["text"], "document.text"),
    )


def _mutation_to_record(mutation: CaseMutation) -> dict[str, object]:
    return {
        "id": mutation.mutation_id,
        "rule_id": mutation.rule_id,
        "relation": mutation.relation.value,
        "edit": {
            "start": mutation.edit.start,
            "before": list(mutation.edit.before),
            "after": list(mutation.edit.after),
        },
        "parameters": dict(mutation.parameters),
        "seed": mutation.seed,
        "rule_pack": {
            "id": mutation.rule_pack_id,
            "version": mutation.rule_pack_version,
        },
        "unicode_version": mutation.unicode_version,
    }


def _mutation_from_record(record: Mapping[str, object]) -> CaseMutation:
    require_keys(
        record,
        {
            "id",
            "rule_id",
            "relation",
            "edit",
            "parameters",
            "seed",
            "rule_pack",
            "unicode_version",
        },
        "mutation",
    )
    relation_value = string(record["relation"], "mutation.relation")
    try:
        relation = Relation(relation_value)
    except ValueError as error:
        raise ValueError(f"invalid mutation relation: {relation_value!r}") from error
    parameters_record = mapping(record["parameters"], "mutation.parameters")
    parameters = tuple(
        sorted(
            (
                string(key, "mutation parameter name"),
                string(value, f"mutation.parameters.{key}"),
            )
            for key, value in parameters_record.items()
        )
    )
    edit_record = mapping(record["edit"], "mutation.edit")
    require_keys(edit_record, {"start", "before", "after"}, "mutation.edit")
    pack_record = mapping(record["rule_pack"], "mutation.rule_pack")
    require_keys(pack_record, {"id", "version"}, "mutation.rule_pack")
    return CaseMutation(
        mutation_id=string(record["id"], "mutation.id"),
        rule_id=string(record["rule_id"], "mutation.rule_id"),
        relation=relation,
        edit=GraphemeEdit(
            start=integer(edit_record["start"], "mutation.edit.start"),
            before=tuple(
                string(item, "mutation.edit.before item")
                for item in array(edit_record["before"], "mutation.edit.before")
            ),
            after=tuple(
                string(item, "mutation.edit.after item")
                for item in array(edit_record["after"], "mutation.edit.after")
            ),
        ),
        parameters=parameters,
        seed=nullable_integer(record["seed"], "mutation.seed"),
        rule_pack_id=string(pack_record["id"], "mutation.rule_pack.id"),
        rule_pack_version=string(pack_record["version"], "mutation.rule_pack.version"),
        unicode_version=nullable_string(record["unicode_version"], "mutation.unicode_version"),
    )


def _engine_digest() -> str:
    package = Path(__file__).parent
    digest = hashlib.sha256()
    for relative_path in _ENGINE_PATHS:
        path = package / relative_path
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_rank(rank: int | None, name: str) -> None:
    if rank is not None and (type(rank) is not int or rank <= 0):
        raise ValueError(f"{name} must be a positive integer or null")
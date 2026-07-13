"""Failure reduction for deterministic text mutations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from orthodrift.text import GraphemeEdit, apply_grapheme_edits

FailureOracle = Callable[[str], bool]


class Minimality(StrEnum):
    GLOBAL = "global"
    ONE_MINIMAL = "one-minimal"


@dataclass(frozen=True, slots=True)
class ReductionTrial:
    edit_indexes: tuple[int, ...]
    text: str
    failed: bool


@dataclass(frozen=True, slots=True)
class ReductionResult:
    source: str
    original_edits: tuple[GraphemeEdit, ...]
    reduced_indexes: tuple[int, ...]
    reduced_edits: tuple[GraphemeEdit, ...]
    text: str
    minimality: Minimality
    trials: tuple[ReductionTrial, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.minimality, Minimality):
            raise ValueError("minimality must be a Minimality value")
        apply_grapheme_edits(self.source, self.original_edits)

        if self.reduced_indexes != tuple(sorted(set(self.reduced_indexes))):
            raise ValueError("reduced indexes must be sorted and unique")
        if any(index < 0 or index >= len(self.original_edits) for index in self.reduced_indexes):
            raise ValueError("reduced index is outside original_edits")

        expected_edits = tuple(self.original_edits[index] for index in self.reduced_indexes)
        if self.reduced_edits != expected_edits:
            raise ValueError("reduced edits do not match reduced indexes")
        if apply_grapheme_edits(self.source, expected_edits) != self.text:
            raise ValueError("reduced edits do not reconstruct result text")

        trials_by_indexes: dict[tuple[int, ...], ReductionTrial] = {}
        for trial in self.trials:
            if type(trial.failed) is not bool:
                raise ValueError("trial failed flag must be boolean")
            if trial.edit_indexes != tuple(sorted(set(trial.edit_indexes))):
                raise ValueError("trial indexes must be sorted and unique")
            if any(index < 0 or index >= len(self.original_edits) for index in trial.edit_indexes):
                raise ValueError("trial index is outside original_edits")
            if trial.edit_indexes in trials_by_indexes:
                raise ValueError("trial edit indexes must be unique")

            trial_edits = tuple(self.original_edits[index] for index in trial.edit_indexes)
            if apply_grapheme_edits(self.source, trial_edits) != trial.text:
                raise ValueError("trial edits do not reconstruct trial text")
            trials_by_indexes[trial.edit_indexes] = trial

        baseline = trials_by_indexes.get(())
        full = trials_by_indexes.get(tuple(range(len(self.original_edits))))
        if baseline is None or baseline.failed:
            raise ValueError("result must contain a passing baseline trial")
        if full is None or not full.failed:
            raise ValueError("result must contain a failing full-edit trial")
        reduced_trial = trials_by_indexes.get(self.reduced_indexes)
        if reduced_trial is None or not reduced_trial.failed:
            raise ValueError("result must contain a failing reduced-edit trial")

    @property
    def evaluations(self) -> int:
        return len(self.trials)


def reduce_failure(
    source: str,
    edits: tuple[GraphemeEdit, ...],
    failure_oracle: FailureOracle,
    *,
    proof_budget: int = 4_096,
) -> ReductionResult:
    """Reduce a deterministic failure and state how strongly minimality was proved.

    All edits must address the same source string. Global minimality means the
    returned subset has the fewest supplied edit units, not necessarily the fewest
    Unicode code points. ``proof_budget`` limits only additional exhaustive-search
    oracle calls; baseline validation and one-minimal reduction are not capped.
    """

    if proof_budget < 0:
        raise ValueError("proof_budget must be non-negative")

    apply_grapheme_edits(source, edits)
    trials: list[ReductionTrial] = []
    cache: dict[tuple[int, ...], bool] = {}

    def evaluate(indexes: tuple[int, ...]) -> bool:
        key = tuple(sorted(indexes))
        if key not in cache:
            candidate_edits = tuple(edits[index] for index in key)
            candidate_text = apply_grapheme_edits(source, candidate_edits)
            failed = bool(failure_oracle(candidate_text))
            cache[key] = failed
            trials.append(ReductionTrial(edit_indexes=key, text=candidate_text, failed=failed))
        return cache[key]

    full = tuple(range(len(edits)))
    if evaluate(()) is True:
        raise ValueError("the unmodified source already fails the oracle")
    if evaluate(full) is False:
        raise ValueError("the complete edit set does not fail the oracle")

    reduced = _ddmin(full, evaluate)
    reduced = _ensure_one_minimal(reduced, evaluate)
    minimality = Minimality.ONE_MINIMAL

    if len(reduced) == 1:
        minimality = Minimality.GLOBAL
    elif proof_budget:
        proof_evaluations = 0
        proof_exhausted = False

        for size in range(1, len(reduced)):
            for candidate in combinations(full, size):
                if candidate not in cache:
                    if proof_evaluations >= proof_budget:
                        proof_exhausted = True
                        break
                    proof_evaluations += 1
                if evaluate(candidate):
                    reduced = candidate
                    minimality = Minimality.GLOBAL
                    proof_exhausted = False
                    break
            if minimality is Minimality.GLOBAL or proof_exhausted:
                break

        if not proof_exhausted and minimality is not Minimality.GLOBAL:
            minimality = Minimality.GLOBAL

    reduced_edits = tuple(edits[index] for index in reduced)
    return ReductionResult(
        source=source,
        original_edits=edits,
        reduced_indexes=reduced,
        reduced_edits=reduced_edits,
        text=apply_grapheme_edits(source, reduced_edits),
        minimality=minimality,
        trials=tuple(trials),
    )


def _ddmin(
    indexes: tuple[int, ...],
    evaluate: Callable[[tuple[int, ...]], bool],
) -> tuple[int, ...]:
    current = indexes
    granularity = 2

    while len(current) >= 2:
        chunks = _partition(current, granularity)
        reduced = False

        for chunk in chunks:
            if evaluate(chunk):
                current = chunk
                granularity = min(len(current), max(granularity - 1, 2))
                reduced = True
                break
        if reduced:
            continue

        for chunk in chunks:
            removed = set(chunk)
            complement = tuple(index for index in current if index not in removed)
            if evaluate(complement):
                current = complement
                granularity = min(len(current), max(granularity - 1, 2))
                reduced = True
                break
        if reduced:
            continue

        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)

    return current


def _ensure_one_minimal(
    indexes: tuple[int, ...],
    evaluate: Callable[[tuple[int, ...]], bool],
) -> tuple[int, ...]:
    current = indexes
    while len(current) > 1:
        for position in range(len(current)):
            candidate = current[:position] + current[position + 1 :]
            if evaluate(candidate):
                current = candidate
                break
        else:
            return current
    return current


def _partition(indexes: tuple[int, ...], parts: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        indexes[len(indexes) * part // parts : len(indexes) * (part + 1) // parts]
        for part in range(parts)
    )

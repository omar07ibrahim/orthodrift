"""Grapheme-aware text variants and their provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import regex

from orthodrift._schema import string

_GRAPHEME = regex.compile(r"\X")


def graphemes(text: str) -> tuple[str, ...]:
    """Split text into Unicode extended grapheme clusters."""

    string(text, "text")
    return tuple(_GRAPHEME.findall(text))


class Relation(StrEnum):
    """The relationship a transformation claims between two strings."""

    CANONICAL = "canonical"
    ORTHOGRAPHIC = "orthographic"
    CONFUSABLE = "confusable"
    ADVERSARIAL = "adversarial"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class GraphemeEdit:
    """One replacement in the input's grapheme-cluster coordinates."""

    start: int
    before: tuple[str, ...]
    after: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.start) is not int or self.start < 0:
            raise ValueError("edit start must be non-negative")
        if self.before == self.after:
            raise ValueError("an edit must change the text")

        for cluster in (*self.before, *self.after):
            if not cluster or graphemes(cluster) != (cluster,):
                raise ValueError(f"not an extended grapheme cluster: {cluster!r}")
        for clusters in (self.before, self.after):
            if graphemes("".join(clusters)) != clusters:
                raise ValueError("edit tuple is not a valid extended-grapheme partition")

    @classmethod
    def from_text(cls, start: int, before: str, after: str) -> GraphemeEdit:
        return cls(start=start, before=graphemes(before), after=graphemes(after))

    @property
    def end(self) -> int:
        return self.start + len(self.before)


def apply_grapheme_edits(text: str, edits: tuple[GraphemeEdit, ...]) -> str:
    """Apply ordered, non-overlapping edits and verify their input spans."""

    source = graphemes(text)
    result: list[str] = []
    cursor = 0

    for edit in edits:
        if edit.start < cursor:
            raise ValueError("grapheme edits overlap or are not ordered")
        if edit.end > len(source):
            raise ValueError("grapheme edit extends past the input")

        actual = source[edit.start : edit.end]
        if actual != edit.before:
            raise ValueError(
                f"grapheme edit expected {edit.before!r} at {edit.start}, found {actual!r}"
            )

        result.extend(source[cursor : edit.start])
        result.extend(edit.after)
        cursor = edit.end

    result.extend(source[cursor:])
    output = "".join(result)
    if graphemes(output) != tuple(result):
        raise ValueError("grapheme edits create an invalid output-cluster boundary")
    return output


def diff_graphemes(before: str, after: str) -> tuple[GraphemeEdit, ...]:
    """Return a minimum-cost Levenshtein script in grapheme coordinates."""

    source = graphemes(before)
    target = graphemes(after)
    prefix = 0
    while prefix < min(len(source), len(target)) and source[prefix] == target[prefix]:
        prefix += 1

    source_end = len(source)
    target_end = len(target)
    while (
        source_end > prefix
        and target_end > prefix
        and source[source_end - 1] == target[target_end - 1]
    ):
        source_end -= 1
        target_end -= 1

    source_middle = source[prefix:source_end]
    target_middle = target[prefix:target_end]
    alignment = _minimum_alignment(source_middle, target_middle)

    edits: list[GraphemeEdit] = []
    edit_start: int | None = None
    removed: list[str] = []
    inserted: list[str] = []
    source_index = prefix

    def flush() -> None:
        nonlocal edit_start
        if edit_start is None:
            return
        edits.append(GraphemeEdit(start=edit_start, before=tuple(removed), after=tuple(inserted)))
        edit_start = None
        removed.clear()
        inserted.clear()

    for source_cluster, target_cluster in alignment:
        if source_cluster is not None and source_cluster == target_cluster:
            flush()
            source_index += 1
            continue

        if edit_start is None:
            edit_start = source_index
        if source_cluster is not None:
            removed.append(source_cluster)
            source_index += 1
        if target_cluster is not None:
            inserted.append(target_cluster)

    flush()
    return tuple(edits)


def _minimum_alignment(
    source: tuple[str, ...], target: tuple[str, ...]
) -> tuple[tuple[str | None, str | None], ...]:
    if not source:
        return tuple((None, cluster) for cluster in target)
    if not target:
        return tuple((cluster, None) for cluster in source)
    if source == target:
        return tuple(zip(source, target, strict=True))
    if len(source) == 1 or len(target) == 1:
        return _small_alignment(source, target)

    source_split = len(source) // 2
    left_costs = _distance_row(source[:source_split], target)
    right_costs = _distance_row(
        tuple(reversed(source[source_split:])),
        tuple(reversed(target)),
    )
    target_split = min(
        range(len(target) + 1),
        key=lambda index: left_costs[index] + right_costs[len(target) - index],
    )

    return (
        *_minimum_alignment(source[:source_split], target[:target_split]),
        *_minimum_alignment(source[source_split:], target[target_split:]),
    )


def _distance_row(source: tuple[str, ...], target: tuple[str, ...]) -> list[int]:
    previous = list(range(len(target) + 1))
    for source_index, source_cluster in enumerate(source, start=1):
        current = [source_index]
        for target_index, target_cluster in enumerate(target, start=1):
            current.append(
                min(
                    previous[target_index] + 1,
                    current[target_index - 1] + 1,
                    previous[target_index - 1] + (source_cluster != target_cluster),
                )
            )
        previous = current
    return previous


def _small_alignment(
    source: tuple[str, ...], target: tuple[str, ...]
) -> tuple[tuple[str | None, str | None], ...]:
    costs = [[0] * (len(target) + 1) for _ in range(len(source) + 1)]
    for source_index in range(1, len(source) + 1):
        costs[source_index][0] = source_index
    for target_index in range(1, len(target) + 1):
        costs[0][target_index] = target_index

    for source_index, source_cluster in enumerate(source, start=1):
        for target_index, target_cluster in enumerate(target, start=1):
            substitution = costs[source_index - 1][target_index - 1]
            if source_cluster != target_cluster:
                substitution += 1
            costs[source_index][target_index] = min(
                substitution,
                costs[source_index - 1][target_index] + 1,
                costs[source_index][target_index - 1] + 1,
            )

    source_index = len(source)
    target_index = len(target)
    reversed_alignment: list[tuple[str | None, str | None]] = []
    while source_index or target_index:
        if (
            source_index
            and target_index
            and source[source_index - 1] == target[target_index - 1]
            and costs[source_index][target_index] == costs[source_index - 1][target_index - 1]
        ):
            reversed_alignment.append((source[source_index - 1], target[target_index - 1]))
            source_index -= 1
            target_index -= 1
        elif (
            source_index
            and target_index
            and costs[source_index][target_index] == costs[source_index - 1][target_index - 1] + 1
        ):
            reversed_alignment.append((source[source_index - 1], target[target_index - 1]))
            source_index -= 1
            target_index -= 1
        elif (
            source_index
            and costs[source_index][target_index] == costs[source_index - 1][target_index] + 1
        ):
            reversed_alignment.append((source[source_index - 1], None))
            source_index -= 1
        else:
            reversed_alignment.append((None, target[target_index - 1]))
            target_index -= 1

    reversed_alignment.reverse()
    return tuple(reversed_alignment)


@dataclass(frozen=True, slots=True)
class TransformStep:
    """A transformation whose output can be reconstructed from recorded edits."""

    rule_id: str
    relation: Relation
    input_text: str
    output_text: str
    edits: tuple[GraphemeEdit, ...]
    parameters: tuple[tuple[str, str], ...] = ()
    seed: int | None = None

    def __post_init__(self) -> None:
        if not self.rule_id or self.rule_id.strip() != self.rule_id:
            raise ValueError("rule_id must be a non-empty, trimmed string")
        if any(character.isspace() for character in self.rule_id):
            raise ValueError("rule_id cannot contain whitespace")
        if not self.edits:
            raise ValueError("a transform step must contain at least one edit")
        if self.seed is not None and type(self.seed) is not int:
            raise ValueError("seed must be an integer or null")

        keys = [key for key, _ in self.parameters]
        if any(not key or key.strip() != key for key in keys):
            raise ValueError("parameter names must be non-empty and trimmed")
        if len(keys) != len(set(keys)):
            raise ValueError("parameter names must be unique")

        reconstructed = apply_grapheme_edits(self.input_text, self.edits)
        if reconstructed != self.output_text:
            raise ValueError("recorded edits do not reconstruct output_text")
        if self.input_text == self.output_text:
            raise ValueError("a transform step must change the text")

    @classmethod
    def from_edits(
        cls,
        *,
        rule_id: str,
        relation: Relation,
        input_text: str,
        edits: tuple[GraphemeEdit, ...],
        parameters: tuple[tuple[str, str], ...] = (),
        seed: int | None = None,
    ) -> TransformStep:
        return cls(
            rule_id=rule_id,
            relation=relation,
            input_text=input_text,
            output_text=apply_grapheme_edits(input_text, edits),
            edits=edits,
            parameters=parameters,
            seed=seed,
        )


@dataclass(frozen=True, slots=True)
class TextVariant:
    """A source string and a verified chain of transformations."""

    source: str
    text: str
    steps: tuple[TransformStep, ...] = ()

    def __post_init__(self) -> None:
        current = self.source
        for step in self.steps:
            if step.input_text != current:
                raise ValueError("transform chain does not match the preceding text")
            current = step.output_text
        if current != self.text:
            raise ValueError("variant text does not match its transform chain")

    @classmethod
    def original(cls, text: str) -> TextVariant:
        return cls(source=text, text=text)

    def apply(self, step: TransformStep) -> TextVariant:
        if step.input_text != self.text:
            raise ValueError("transform input does not match the current variant")
        return TextVariant(
            source=self.source,
            text=step.output_text,
            steps=(*self.steps, step),
        )

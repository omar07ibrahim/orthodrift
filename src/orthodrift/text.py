"""Grapheme-aware text variants and their provenance."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

import regex

_GRAPHEME = regex.compile(r"\X")


def graphemes(text: str) -> tuple[str, ...]:
    """Split text into Unicode extended grapheme clusters."""

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
        if self.start < 0:
            raise ValueError("edit start must be non-negative")
        if self.before == self.after:
            raise ValueError("an edit must change the text")

        for cluster in (*self.before, *self.after):
            if not cluster or graphemes(cluster) != (cluster,):
                raise ValueError(f"not an extended grapheme cluster: {cluster!r}")

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
    previous: GraphemeEdit | None = None

    for edit in edits:
        if edit.start < cursor:
            raise ValueError("grapheme edits overlap or are not ordered")
        if previous and not previous.before and edit.start == previous.start:
            raise ValueError("multiple insertions at one boundary are ambiguous")
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
        previous = edit

    result.extend(source[cursor:])
    return "".join(result)


def diff_graphemes(before: str, after: str) -> tuple[GraphemeEdit, ...]:
    """Describe a string change in the source's grapheme coordinates."""

    source = graphemes(before)
    target = graphemes(after)
    matcher = SequenceMatcher(a=source, b=target, autojunk=False)
    edits: list[GraphemeEdit] = []

    for operation, source_start, source_end, target_start, target_end in matcher.get_opcodes():
        if operation == "equal":
            continue
        edits.append(
            GraphemeEdit(
                start=source_start,
                before=source[source_start:source_end],
                after=target[target_start:target_end],
            )
        )

    return tuple(edits)


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

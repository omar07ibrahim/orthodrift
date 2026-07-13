"""Validation for the built-in mutation rules accepted by case v1."""

from __future__ import annotations

import re
import unicodedata

from orthodrift.text import GraphemeEdit, Relation, diff_graphemes

_UNICODE_PACK = ("unicode-normalization", "1")
_ADVERSARIAL_PACK = ("orthodrift-adversarial", "0.1.0a0")
_SUPPORTED_UNICODE_VERSIONS = {"16.0.0"}
_DELTA = re.compile(r"-?(?:0|[1-9][0-9]{0,17})\Z")


def validate_rule_claim(
    *,
    rule_id: str,
    relation: Relation,
    edit: GraphemeEdit,
    parameters: tuple[tuple[str, str], ...],
    rule_pack_id: str,
    rule_pack_version: str,
    unicode_version: str | None,
    input_text: str,
    output_text: str,
) -> None:
    if rule_id == "unicode.normalize-span.nfd":
        _require_metadata(
            rule_id=rule_id,
            relation=relation,
            expected_relation=Relation.CANONICAL,
            parameters=parameters,
            expected_parameters=(("form", "NFD"), ("scope", "edit-span")),
            rule_pack=(rule_pack_id, rule_pack_version),
            expected_pack=_UNICODE_PACK,
        )
        if unicode_version not in _SUPPORTED_UNICODE_VERSIONS:
            raise ValueError(f"unsupported Unicode version for {rule_id}: {unicode_version!r}")
        before = "".join(edit.before)
        after = "".join(edit.after)
        if after != unicodedata.normalize("NFD", before):
            raise ValueError(f"edit does not reproduce registered rule {rule_id!r}")
        local_edits = diff_graphemes(before, after)
        if len(local_edits) != 1:
            raise ValueError(f"{rule_id!r} mutation must contain one minimal edit span")
        local = local_edits[0]
        expected = GraphemeEdit(
            start=edit.start + local.start,
            before=local.before,
            after=local.after,
        )
        if edit != expected:
            raise ValueError(f"{rule_id!r} mutation is not a minimal edit span")
        return

    if rule_id == "adversarial.ascii-uppercase":
        _require_metadata(
            rule_id=rule_id,
            relation=relation,
            expected_relation=Relation.ADVERSARIAL,
            parameters=parameters,
            expected_parameters=(),
            rule_pack=(rule_pack_id, rule_pack_version),
            expected_pack=_ADVERSARIAL_PACK,
        )
        _require_no_unicode_version(rule_id, unicode_version)
        before = "".join(edit.before)
        after = "".join(edit.after)
        if not before or any(character < "a" or character > "z" for character in before):
            raise ValueError("ASCII-uppercase rule requires lowercase ASCII input")
        if after != before.upper():
            raise ValueError("ASCII-uppercase edit does not match its registered rule")
        return

    if rule_id == "adversarial.numeric-shift":
        _require_metadata(
            rule_id=rule_id,
            relation=relation,
            expected_relation=Relation.ADVERSARIAL,
            parameters=parameters,
            expected_parameters=parameters,
            rule_pack=(rule_pack_id, rule_pack_version),
            expected_pack=_ADVERSARIAL_PACK,
        )
        _require_no_unicode_version(rule_id, unicode_version)
        if len(parameters) != 1 or parameters[0][0] != "delta":
            raise ValueError("numeric-shift rule requires exactly one delta parameter")
        delta_text = parameters[0][1]
        if _DELTA.fullmatch(delta_text) is None:
            raise ValueError("numeric-shift delta must be a bounded canonical integer")
        before = "".join(edit.before)
        after = "".join(edit.after)
        if not before or not before.isascii() or not before.isdecimal():
            raise ValueError("numeric-shift rule requires ASCII digits")
        if not after.isascii() or not after.isdecimal() or len(after) != len(before):
            raise ValueError("numeric-shift output must preserve the ASCII digit width")
        shifted = int(before) + int(delta_text)
        if shifted < 0 or str(shifted).zfill(len(before)) != after:
            raise ValueError("numeric-shift edit does not match its registered delta")
        return

    raise ValueError(f"unsupported mutation rule: {rule_id!r}")


def _require_metadata(
    *,
    rule_id: str,
    relation: Relation,
    expected_relation: Relation,
    parameters: tuple[tuple[str, str], ...],
    expected_parameters: tuple[tuple[str, str], ...],
    rule_pack: tuple[str, str],
    expected_pack: tuple[str, str],
) -> None:
    if relation is not expected_relation:
        raise ValueError(f"relation does not match registered rule {rule_id!r}")
    if parameters != expected_parameters:
        raise ValueError(f"parameters do not match registered rule {rule_id!r}")
    if rule_pack != expected_pack:
        raise ValueError(f"rule pack does not match registered rule {rule_id!r}")


def _require_no_unicode_version(rule_id: str, unicode_version: str | None) -> None:
    if unicode_version is not None:
        raise ValueError(f"{rule_id!r} must not claim a Unicode data version")

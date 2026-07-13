"""Strict JSON schema primitives shared by versioned artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from math import isfinite


def loads_mapping(text: str, name: str) -> Mapping[str, object]:
    try:
        value: object = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid {name} JSON") from error
    except RecursionError as error:
        raise ValueError(f"{name} JSON nesting is too deep") from error
    record = mapping(value, name)
    _validate_json_value(record, name)
    return record


def canonical_dumps(record: Mapping[str, object]) -> str:
    _validate_json_value(record, "record")
    try:
        return json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except RecursionError as error:
        raise ValueError("record nesting is too deep") from error


def require_keys(record: Mapping[str, object], expected: set[str], name: str) -> None:
    actual = set(record)
    if actual != expected:
        raise ValueError(
            f"{name} fields do not match schema; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    return value


def array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{name} must contain only Unicode scalar values")
    return value


def integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def nullable_integer(value: object, name: str) -> int | None:
    return None if value is None else integer(value, name)


def nullable_string(value: object, name: str) -> str | None:
    return None if value is None else string(value, name)


def boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    record: dict[str, object] = {}
    for key, value in pairs:
        string(key, "JSON field name")
        if key in record:
            raise ValueError(f"duplicate JSON field: {key!r}")
        record[key] = value
    return record


def _reject_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _validate_json_value(value: object, name: str) -> None:
    maximum_depth = 256
    pending: list[tuple[object, str, int]] = [(value, name, 0)]
    while pending:
        item, item_name, depth = pending.pop()
        if depth > maximum_depth:
            raise ValueError(f"{name} nesting exceeds {maximum_depth} levels")
        if item is None or type(item) in {bool, int}:
            continue
        if isinstance(item, float):
            if not isfinite(item):
                raise ValueError(f"{item_name} must contain only finite numbers")
            continue
        if isinstance(item, str):
            string(item, item_name)
            continue
        if isinstance(item, Mapping):
            for key, child in item.items():
                scalar_key = string(key, f"{item_name} field name")
                pending.append((child, f"{item_name}.{scalar_key}", depth + 1))
            continue
        if isinstance(item, (list, tuple)):
            pending.extend(
                (child, f"{item_name}[{index}]", depth + 1) for index, child in enumerate(item)
            )
            continue
        raise ValueError(f"{item_name} contains a value that JSON cannot represent")

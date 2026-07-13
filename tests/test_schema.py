import pytest

from orthodrift._schema import canonical_dumps, loads_mapping, number


def test_strict_json_rejects_nonstandard_and_overflowed_numbers() -> None:
    for text in ('{"value":NaN}', '{"value":Infinity}', '{"value":1e400}'):
        with pytest.raises(ValueError):
            loads_mapping(text, "test")


def test_number_normalizes_integer_overflow_to_a_validation_error() -> None:
    with pytest.raises(ValueError, match="finite number"):
        number(10**1000, "value")


def test_canonical_json_rejects_programmatic_surrogates() -> None:
    with pytest.raises(ValueError, match="Unicode scalar values"):
        canonical_dumps({"nested": ["\ud800"]})


def test_deep_json_nesting_is_a_controlled_validation_error() -> None:
    text = '{"nested":' + "[" * 1_100 + "0" + "]" * 1_100 + "}"

    with pytest.raises(ValueError, match="nesting"):
        loads_mapping(text, "test")

    value: object = 0
    for _ in range(300):
        value = [value]
    with pytest.raises(ValueError, match="nesting"):
        canonical_dumps({"nested": value})

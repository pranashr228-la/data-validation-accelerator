from dva.config.models import HashDefaults
from dva.normalization.rules import hash_row, normalize_value


def test_null_becomes_null_token():
    defaults = HashDefaults(null_token="<NULL>")
    assert normalize_value(None, defaults) == "<NULL>"


def test_trim_and_case_insensitive_by_default():
    defaults = HashDefaults(trim_strings=True, case_sensitive=False)
    assert normalize_value("  Hello  ", defaults) == "HELLO"


def test_case_sensitive_preserves_case():
    defaults = HashDefaults(case_sensitive=True)
    assert normalize_value("Hello", defaults) == "Hello"


def test_empty_string_as_null():
    defaults = HashDefaults(empty_string_as_null=True, trim_strings=True, null_token="<NULL>")
    assert normalize_value("   ", defaults) == "<NULL>"


def test_decimal_rounding_is_deterministic():
    defaults = HashDefaults(decimal_scale=2)
    assert normalize_value(1.005, defaults) in {"1.00", "1.01"}  # banker's/away-from-zero rounding
    assert normalize_value(10, defaults) == "10"


def test_hash_row_is_deterministic_and_order_sensitive():
    defaults = HashDefaults()
    h1 = hash_row(["a", "b", 1], defaults)
    h2 = hash_row(["a", "b", 1], defaults)
    h3 = hash_row(["b", "a", 1], defaults)
    assert h1 == h2
    assert h1 != h3


def test_hash_row_case_insensitive_matches_across_case():
    defaults = HashDefaults(case_sensitive=False)
    assert hash_row(["Active"], defaults) == hash_row(["ACTIVE"], defaults)

from dva.config.models import ToleranceConfig
from dva.validations.base import compare_values


def test_within_tolerance_passes():
    tolerance = ToleranceConfig(type="percentage", warning=1.0, failure=5.0)
    _, _, status = compare_values(100.0, 99.5, tolerance)
    assert status == "PASS"


def test_warning_band():
    tolerance = ToleranceConfig(type="percentage", warning=1.0, failure=5.0)
    _, _, status = compare_values(100.0, 97.0, tolerance)
    assert status == "WARN"


def test_failure_band():
    tolerance = ToleranceConfig(type="percentage", warning=1.0, failure=5.0)
    _, _, status = compare_values(100.0, 80.0, tolerance)
    assert status == "FAIL"


def test_absolute_tolerance():
    tolerance = ToleranceConfig(type="absolute", warning=1.0, failure=5.0)
    difference, _, status = compare_values(100.0, 94.0, tolerance)
    assert difference == 6.0
    assert status == "FAIL"


def test_none_values_pass_when_both_none():
    tolerance = ToleranceConfig()
    _, _, status = compare_values(None, None, tolerance)
    assert status == "PASS"


def test_none_values_fail_when_only_one_none():
    tolerance = ToleranceConfig()
    _, _, status = compare_values(None, 10.0, tolerance)
    assert status == "FAIL"

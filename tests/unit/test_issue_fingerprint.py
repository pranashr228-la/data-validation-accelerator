from dva.issues.fingerprint import compute_fingerprint


def test_fingerprint_is_stable_for_same_inputs():
    f1 = compute_fingerprint(
        dataset_name="ds", rule_name="count", rule_type="count", issue_type="count_mismatch"
    )
    f2 = compute_fingerprint(
        dataset_name="ds", rule_name="count", rule_type="count", issue_type="count_mismatch"
    )
    assert f1 == f2


def test_fingerprint_differs_for_different_inputs():
    f1 = compute_fingerprint(
        dataset_name="ds", rule_name="count", rule_type="count", issue_type="count_mismatch"
    )
    f2 = compute_fingerprint(
        dataset_name="ds2", rule_name="count", rule_type="count", issue_type="count_mismatch"
    )
    assert f1 != f2


def test_fingerprint_excludes_run_id_by_construction():
    # compute_fingerprint has no run_id parameter at all -- this test
    # documents that guarantee so a future signature change is caught.
    import inspect

    params = inspect.signature(compute_fingerprint).parameters
    assert "run_id" not in params
